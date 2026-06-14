import json
import os

import anthropic

from .fetcher import Job

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _format_experiences(experiences: list[dict]) -> str:
    lines = []
    for i, exp in enumerate(experiences):
        lines.append(f"[{i}] {exp['company']} | {exp['role']} | {exp['time']}")
        for b in exp.get("bullets", []):
            lines.append(f"    - {b}")
    return "\n".join(lines)


def sonnet_analyze(job: Job, skills_str: str, experiences: list[dict], grad_flag_hint: bool) -> dict:
    """
    Ranks experiences by relevance to the job and rewrites their bullets
    to mirror the job posting's language and keywords.

    Returns:
        fit_score, skills_matched, grad_flag, ranked_experiences
        where ranked_experiences is ordered most → least relevant,
        each with optimized_bullets tailored to this specific job.
    """
    exp_text = _format_experiences(experiences)

    prompt = f"""You are an expert resume coach helping a candidate tailor their application.

Candidate skills: {skills_str}

Job posting:
Company: {job.company}
Role: {job.role}
Location: {job.location}
Notes: {job.notes or "N/A"}
Grad flag hint (may require 2028 graduation): {grad_flag_hint}

Candidate's experiences (indexed for reference):
{exp_text}

Tasks:
1. Score the overall fit (1-10) between the candidate and this role.
2. List which of the candidate's skills are relevant to this role.
3. Rank ALL experiences from most to least relevant for this specific job.
4. For the top 3 most relevant experiences, rewrite 2 of their bullets each to:
   - Mirror the job posting's specific language and keywords
   - Keep the original achievement/metric intact
   - Start with a strong action verb
   - Sound like they were written for THIS role

Return JSON only:
{{
  "fit_score": <1-10>,
  "skills_matched": ["skill1", "skill2"],
  "grad_flag": <true only if role requires 2028 graduation as hard requirement>,
  "ranked_experiences": [
    {{
      "index": <original index from list above>,
      "company": "...",
      "role": "...",
      "optimized_bullets": ["rewritten bullet 1", "rewritten bullet 2"]
    }},
    ...
  ]
}}

Include ALL experiences in ranked_experiences (all {len(experiences)} of them), ordered most to least relevant.
Only provide optimized_bullets for the top 3; set optimized_bullets to [] for the rest."""

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"Stage 2 JSON parse error for {job.company} — {job.role}:\n{text}")
        return {
            "fit_score": 0,
            "skills_matched": [],
            "grad_flag": grad_flag_hint,
            "ranked_experiences": [],
        }
