"""
Stage 2c (opt-in, not yet wired into main.py): tailors bullets for a whitelisted
subset of resume experiences (config.LATEX_TAILOR_COMPANIES) to a specific job's
requirements, and emits ready-to-paste LaTeX matching resume.tex's macros.

Two hard gates keep this from running away:
  1. config.LATEX_TAILOR_COMPANIES — only experiences whose `id` is in this list
     are ever sent to Sonnet. Empty by default; populate it with the companies
     worth tailoring.
  2. MAX_LATEX_REWRITES_PER_DAY — a hard cap on Sonnet calls per calendar day,
     persisted in data/latex_tailor_budget.json so it holds across manual re-runs
     on the same day, not just within one pipeline run.

Sonnet is instructed to only reword a bullet when the job requirements give a
genuine, specific reason to, and to leave the rest untouched — "changed": false
entries are skipped, so a job with no real overlap produces no file at all.
"""

import json
import os
import re
from datetime import date
from pathlib import Path

import anthropic

import config
from .fetcher import Job

MAX_LATEX_REWRITES_PER_DAY = 5

_BUDGET_STATE_PATH = Path("data/latex_tailor_budget.json")
OUTPUT_DIR = Path("tailored_bullets")

_client = None

_LATEX_TEMPLATES = {
    "experience": (
        "\\resumeSubheading\n"
        "  {{{role}}}{{{time}}}\n"
        "  {{{company}}}{{{location}}}\n"
        "  \\resumeItemListStart\n"
        "{items}"
        "  \\resumeItemListEnd"
    ),
    "project": (
        "\\resumeProjectHeading\n"
        "    {{\\textbf{{{company}}} $|$ \\emph{{{tech_stack}}}}}{{{time}}}\n"
        "    \\resumeItemListStart\n"
        "{items}"
        "    \\resumeItemListEnd"
    ),
}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _load_budget_state() -> dict:
    try:
        with open(_BUDGET_STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"date": "", "count": 0}


def _save_budget_state(state: dict) -> None:
    _BUDGET_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_BUDGET_STATE_PATH, "w") as f:
        json.dump(state, f)


def _consume_budget(max_per_day: int) -> bool:
    """Atomically checks-and-increments today's rewrite count. Returns False if the cap is hit."""
    today = date.today().isoformat()
    state = _load_budget_state()
    if state.get("date") != today:
        state = {"date": today, "count": 0}
    if state["count"] >= max_per_day:
        return False
    state["count"] += 1
    _save_budget_state(state)
    return True


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _render_block(exp: dict, bullets: list[str]) -> str:
    items = "".join(f"    \\resumeItem{{{b}}}\n" for b in bullets)
    return _LATEX_TEMPLATES[exp["section"]].format(items=items, **exp)


def tailor_latex_bullets(job: Job, experiences: list[dict], max_per_day: int = MAX_LATEX_REWRITES_PER_DAY) -> str | None:
    """
    Returns the path to a written .txt snippet containing the LaTeX block(s) for
    every whitelisted experience Sonnet actually chose to reword, or None if:
      - no experience in `experiences` is on config.LATEX_TAILOR_COMPANIES,
      - today's MAX_LATEX_REWRITES_PER_DAY budget is exhausted,
      - the response failed to parse, or
      - Sonnet decided none of the eligible experiences were worth touching.
    """
    eligible = [e for e in experiences if e.get("id") in config.LATEX_TAILOR_COMPANIES]
    if not eligible:
        return None

    if not _consume_budget(max_per_day):
        print(f"[latex_tailor] daily cap ({max_per_day}) reached — skipping {job.company}")
        return None

    exp_blocks = "\n\n".join(
        f"[{e['id']}] {e['company']} | {e['role']}\n"
        + "\n".join(f"- ({len(b)} chars) {b}" for b in e["bullets"])
        for e in eligible
    )

    req_section = (
        f"Job requirements:\n{job.requirements[:800]}"
        if job.requirements
        else f"No requirements page available — infer from role title: {job.role}"
    )

    prompt = f"""You are tailoring specific resume bullets for one job application.

Do NOT force changes. Only reword a bullet when the job requirements give a genuine,
specific reason to (shared technology, a named skill, a matching domain). If an
experience has no real overlap with this job, leave it completely unchanged.

Job: {job.role} at {job.company}
{req_section}

Candidate experiences eligible for tailoring:
{exp_blocks}

Rules:
- Never invent skills, tools, or metrics not already present in the original bullet.
- Keep all original metrics intact.
- Each rewritten bullet must be within \u00b12 characters of the original bullet's length.
- Mirror the job's actual vocabulary — don't add generic buzzwords.

Return a JSON array, one object per eligible experience, in the same order:
[{{"id": "turkish_technology", "changed": true, "bullets": ["rewritten 1", "rewritten 2", "rewritten 3"]}}]
Use "changed": false (and omit or empty "bullets") for any experience you didn't touch."""

    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    text = match.group() if match else raw.strip()
    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        return None

    by_id = {e["id"]: e for e in eligible}
    blocks = []
    for entry in results:
        exp = by_id.get(entry.get("id"))
        if exp is None or not entry.get("changed"):
            continue
        new_bullets = entry.get("bullets") or []
        if len(new_bullets) != len(exp["bullets"]):
            continue
        if any(abs(len(nb) - len(ob)) > 2 for nb, ob in zip(new_bullets, exp["bullets"])):
            continue  # length constraint violated — drop this experience rather than break the LaTeX layout
        blocks.append(_render_block(exp, new_bullets))

    if not blocks:
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{date.today().isoformat()}_{_slugify(job.company)}_{_slugify(job.role)}.txt"
    path = OUTPUT_DIR / fname
    header = f"% Job: {job.role} at {job.company}\n% Apply link: {job.apply_link}\n\n"
    path.write_text(header + "\n\n".join(blocks) + "\n")
    return str(path)
