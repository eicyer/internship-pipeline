import json
import os
import re

import anthropic

from .fetcher import Job

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def haiku_score(job: Job, skills_str: str, experiences: list[dict], grad_flag_hint: bool) -> dict:
    """
    Haiku call: scores job fit and detects graduation year requirements.
    Uses only experience skill buzzwords (not full bullets) — cheap (~250 tokens in, ~80 out).
    Returns: {fit_score, skills_matched, grad_flag, top_indices}
    """
    exp_lines = "\n".join(
        f"[{i}] {e['company']} | {e['role']} | {', '.join(e.get('skills', []))}"
        for i, e in enumerate(experiences)
    )

    req_section = f"\nJob requirements:\n{job.requirements[:600]}" if job.requirements else ""

    prompt = f"""Candidate skills: {skills_str}
Job: {job.role} at {job.company} | {job.location}{req_section}

Rank these experiences by relevance to the job. Pick the top 3 indices.
Also give an overall fit score (1-10), list matched candidate skills, and set grad_flag true only if the job requires 2028 graduation as a hard requirement.

{exp_lines}

JSON only:
{{"fit_score": 7, "skills_matched": ["Python", "SQL"], "grad_flag": false, "top_indices": [0, 3, 4]}}"""

    resp = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    text = match.group() if match else raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"fit_score": 0, "skills_matched": [], "grad_flag": grad_flag_hint, "top_indices": [0, 1, 2]}


def sonnet_rewrite(job: Job, experiences: list[dict]) -> dict:
    """
    Sonnet call: selects the 3 most relevant experiences from the full list,
    then rewrites 2 bullets per experience to match the job's language and keywords.
    Returns: {"ranked_experiences": [...]} matching the shape expected by sheets/notifier.
    """
    exp_blocks = "\n\n".join(
        f"[{i}] {e['company']} | {e['role']}\n"
        + "\n".join(f"- {b}" for b in e.get("bullets", []))
        for i, e in enumerate(experiences)
    )

    req_section = (
        f"Job requirements:\n{job.requirements[:800]}"
        if job.requirements
        else f"No requirements page available — infer from role title: {job.role}"
    )

    prompt = f"""You are tailoring a resume for a job application.

Job: {job.role} at {job.company}
{req_section}

From the {len(experiences)} candidate experiences below, select the 3 most relevant to this specific role
and rewrite exactly 3 bullet points per experience to match the job's language and keywords.
Keep all original metrics intact. Start each bullet with a strong action verb.
Mirror the role's exact technical vocabulary.
Each rewritten bullet must be the same character length as the original bullet it replaces (±2 chars).

{exp_blocks}

Return JSON array of exactly 3 objects ordered by relevance (most relevant first):
[{{"index": 0, "company": "...", "role": "...", "optimized_bullets": ["rewritten 1", "rewritten 2", "rewritten 3"]}}]"""

    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    text = match.group() if match else raw.strip()
    try:
        rewritten = json.loads(text)
    except json.JSONDecodeError:
        rewritten = [
            {"index": i, "company": experiences[i]["company"], "role": experiences[i]["role"], "optimized_bullets": []}
            for i in range(min(3, len(experiences)))
        ]

    # Append remaining experiences (no bullets) so sheets/notifier have the full list
    seen_indices = {entry.get("index", -1) for entry in rewritten}
    ranked_experiences = list(rewritten)
    for i, exp in enumerate(experiences):
        if i not in seen_indices:
            ranked_experiences.append({
                "index": i,
                "company": exp["company"],
                "role": exp["role"],
                "optimized_bullets": [],
            })

    return {"ranked_experiences": ranked_experiences}
