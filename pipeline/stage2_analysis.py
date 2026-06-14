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


def sonnet_analyze(job: Job, skills_str: str, resume_bullets: list[str], grad_flag_hint: bool) -> dict:
    """
    Deep per-job analysis via Sonnet. Returns a dict with:
    fit_score, skills_matched, grad_flag, bullet_suggestions
    """
    bullets_text = "\n".join(f"- {b}" for b in resume_bullets) if resume_bullets else "(none provided)"

    prompt = f"""You are an internship application coach. Analyze this job for the candidate.

Candidate skills: {skills_str}

Candidate's existing resume bullets (for rewrite context):
{bullets_text}

Job posting:
Company: {job.company}
Role: {job.role}
Location: {job.location}
Notes: {job.notes or "N/A"}
Grad flag hint (may require 2028 graduation): {grad_flag_hint}

Return JSON only:
{{
  "fit_score": <1-10 integer>,
  "skills_matched": ["skill1", "skill2"],
  "grad_flag": <true if role explicitly requires 2028 graduation only, else false>,
  "bullet_suggestions": [
    "Quantified, action-verb bullet tailored to this role",
    "Second tailored bullet"
  ]
}}

Rules:
- fit_score: 10 = perfect match on skills and role type, 1 = almost no overlap
- bullet_suggestions: 2-3 bullets, each starting with a strong verb, referencing the candidate's actual skills where possible
- grad_flag: true only if 2028 graduation is a hard requirement (not just preferred)"""

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
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
            "bullet_suggestions": [],
        }
