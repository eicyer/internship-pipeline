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


def _haiku_rank(job: Job, skills_str: str, experiences: list[dict], grad_flag_hint: bool) -> dict:
    """
    Haiku call: uses only experience skill buzzwords (not full bullets) to rank
    experiences and compute fit score. Extremely cheap — ~250 tokens in, ~80 out.
    """
    exp_lines = "\n".join(
        f"[{i}] {e['company']} | {e['role']} | {', '.join(e.get('skills', []))}"
        for i, e in enumerate(experiences)
    )

    prompt = f"""Candidate skills: {skills_str}
Job: {job.role} at {job.company} | {job.location}
Grad flag hint: {grad_flag_hint}

Rank these experiences by relevance to the job. Pick the top 3 indices.
Also give an overall fit score (1-10), list matched candidate skills, and set grad_flag true only if the job requires 2028 graduation as a hard requirement.

{exp_lines}

JSON only:
{{"fit_score": 7, "skills_matched": ["Python", "SQL"], "grad_flag": false, "top_indices": [0, 3, 4]}}"""

    resp = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"fit_score": 0, "skills_matched": [], "grad_flag": grad_flag_hint, "top_indices": [0, 1, 2]}


def _sonnet_rewrite(job: Job, top_experiences: list[dict]) -> list[dict]:
    """
    Sonnet call: receives ONLY the top 3 experiences with their actual bullets.
    Sole task is rewriting — no ranking, no scoring, nothing else.
    ~450 tokens in, ~200 out.
    """
    exp_blocks = "\n\n".join(
        f"[{e['company']} | {e['role']}]\n"
        + "\n".join(f"- {b}" for b in e.get("bullets", []))
        for e in top_experiences
    )

    prompt = f"""Rewrite 2 bullets from each experience to match this job's language and keywords.
Keep original metrics intact. Start with a strong action verb. Mirror the role's technical vocabulary.

Job: {job.role} at {job.company}

{exp_blocks}

JSON only — array ordered same as input:
[{{"company": "...", "role": "...", "optimized_bullets": ["rewritten 1", "rewritten 2"]}}]"""

    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [{"company": e["company"], "role": e["role"], "optimized_bullets": []} for e in top_experiences]


def sonnet_analyze(job: Job, skills_str: str, experiences: list[dict], grad_flag_hint: bool) -> dict:
    """
    Two-sub-call pipeline:
      1. Haiku: buzzword ranking → fit_score, skills_matched, grad_flag, top 3 indices
      2. Sonnet: rewrite bullets for top 3 experiences only

    Returns the same shape as before so sheets/notifier need no changes.
    """
    ranking = _haiku_rank(job, skills_str, experiences, grad_flag_hint)

    top_indices = ranking.get("top_indices", [0, 1, 2])[:3]
    top_experiences = [experiences[i] for i in top_indices if i < len(experiences)]

    rewritten = _sonnet_rewrite(job, top_experiences)

    # Build ranked_experiences: top 3 with rewritten bullets, rest appended without
    seen = set(top_indices)
    ranked_experiences = []
    for i, entry in enumerate(rewritten):
        ranked_experiences.append({
            "index": top_indices[i] if i < len(top_indices) else -1,
            "company": entry.get("company", ""),
            "role": entry.get("role", ""),
            "optimized_bullets": entry.get("optimized_bullets", []),
        })
    for i, exp in enumerate(experiences):
        if i not in seen:
            ranked_experiences.append({
                "index": i,
                "company": exp["company"],
                "role": exp["role"],
                "optimized_bullets": [],
            })

    return {
        "fit_score": ranking.get("fit_score", 0),
        "skills_matched": ranking.get("skills_matched", []),
        "grad_flag": ranking.get("grad_flag", grad_flag_hint),
        "ranked_experiences": ranked_experiences,
    }
