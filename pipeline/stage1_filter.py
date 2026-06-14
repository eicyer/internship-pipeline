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


def haiku_filter(jobs: list[Job], skills_str: str) -> list[tuple[Job, bool]]:
    """
    Single Haiku call filtering all jobs. Returns (job, grad_flag) pairs
    for jobs matching ≥1 candidate skill.
    grad_flag=True means the posting explicitly requires Class of 2028 graduation only.
    """
    if not jobs:
        return []

    job_lines = "\n".join(
        f"[{i}] {j.company} | {j.role} | {j.location}"
        for i, j in enumerate(jobs)
    )

    prompt = f"""Candidate skills: {skills_str}

Filter these internship listings. Return ONLY the IDs of jobs where:
- The role could realistically require at least one of the candidate's skills, OR
- The role title suggests technical work (software, data, ML, engineering, etc.)

Also flag any job that explicitly states "Class of 2028", "graduating 2028", or "2028 only" as a graduation requirement.

Jobs:
{job_lines}

Respond with JSON only, no explanation:
{{"matches": [{{"id": 0, "grad_flag": false}}, ...]}}"""

    response = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"Stage 1 JSON parse error. Raw response:\n{text}")
        return []

    results = []
    for match in data.get("matches", []):
        idx = match.get("id")
        if isinstance(idx, int) and 0 <= idx < len(jobs):
            results.append((jobs[idx], bool(match.get("grad_flag", False))))

    print(f"Stage 1: {len(jobs)} → {len(results)} matches")
    return results
