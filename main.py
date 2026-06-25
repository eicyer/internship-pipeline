import json
import os

STATE_FILE = "data/seen_jobs.json"

# Set MAX_JOBS_PER_REPO=7 locally when testing (~28 jobs total across 4 repos).
# Leave unset in production — the daily cron only sees the delta anyway.
_max = os.getenv("MAX_JOBS_PER_REPO")
MAX_JOBS_PER_REPO: int | None = int(_max) if _max else None

# Only jobs scoring at or above this threshold advance to Sonnet rewriting.
# Target: ~20 jobs/week. Raise to 8 if too many pass, lower to 6 if too few.
FIT_SCORE_THRESHOLD = 7


def load_seen() -> set:
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(links: set) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(links), f, indent=2)


def main() -> None:
    from pipeline.fetcher import fetch_new_jobs
    from pipeline.resume_parser import parse_resume
    from pipeline.stage1_filter import keyword_filter
    from pipeline.requirements_fetcher import fetch_all_requirements
    from pipeline.stage2_analysis import haiku_score, sonnet_rewrite
    from pipeline.sheets import ensure_header, get_existing_links, append_row, get_sheet_url
    from pipeline.notifier import send_telegram

    if MAX_JOBS_PER_REPO:
        print(f"Fetching latest {MAX_JOBS_PER_REPO} jobs per repo (~{MAX_JOBS_PER_REPO * 4} total)")

    seen = load_seen()

    try:
        sheet_links = get_existing_links()
        seen |= sheet_links
    except Exception as e:
        print(f"Could not fetch existing sheet links (continuing): {e}")

    print(f"Loaded {len(seen)} already-seen job links")

    skills_str, experiences = parse_resume()
    print(f"Skills: {skills_str}")
    print(f"Experiences loaded: {len(experiences)}")

    new_jobs = fetch_new_jobs(seen, per_repo=MAX_JOBS_PER_REPO)
    if not new_jobs:
        print("No new jobs found. Done.")
        save_seen(seen)
        return

    # Stage 1: whitelist filter (hardcoded Python, no API calls)
    passing = keyword_filter(new_jobs)

    if not passing:
        print("No matches after Stage 1.")
        save_seen(seen | {j.apply_link for j in new_jobs})
        return

    print(f"\nFetching requirements for {len(passing)} jobs (parallel)...")
    fetch_all_requirements(passing)

    ensure_header()

    # Stage 2a: Haiku scores every Stage 1 passer (cheap)
    print(f"\nStage 2a: Haiku scoring {len(passing)} jobs...")
    scored = []
    for job, grad_flag_hint in passing:
        print(f"  Scoring: {job.company} — {job.role}")
        score = haiku_score(job, skills_str, experiences, grad_flag_hint)
        scored.append((job, score))
        print(f"    fit={score['fit_score']}/10  skills={score['skills_matched']}  grad_flag={score['grad_flag']}")

    # Gate: only high-fit, non-grad-flagged jobs advance to Sonnet
    above_threshold = [
        (job, score) for job, score in scored
        if score["fit_score"] >= FIT_SCORE_THRESHOLD and not score["grad_flag"]
    ]
    below_threshold = [
        (job, score) for job, score in scored
        if score["fit_score"] < FIT_SCORE_THRESHOLD or score["grad_flag"]
    ]

    print(
        f"\nStage 2 gate (fit ≥ {FIT_SCORE_THRESHOLD}, no grad flag): "
        f"{len(scored)} scored → {len(above_threshold)} advance, {len(below_threshold)} dropped"
    )
    for job, score in below_threshold:
        reason = "grad flag" if score["grad_flag"] else f"fit={score['fit_score']}"
        print(f"  Dropped ({reason}): {job.company} — {job.role}")

    if not above_threshold:
        print("No jobs cleared the threshold. Done.")
        save_seen(seen | {j.apply_link for j in new_jobs})
        return

    # Stage 2b: Sonnet selects top 3 experiences and rewrites bullets (only for threshold jobs)
    print(f"\nStage 2b: Sonnet rewriting {len(above_threshold)} jobs...")
    for job, score in above_threshold:
        print(f"  Rewriting: {job.company} — {job.role} (fit={score['fit_score']})")
        rewrite = sonnet_rewrite(job, experiences)
        analysis = {**score, **rewrite}
        row_num = append_row(job, analysis)
        sheet_url = get_sheet_url(row_num)
        send_telegram(job, analysis, sheet_url)

    save_seen(seen | {j.apply_link for j in new_jobs})
    print(f"\nDone. {len(above_threshold)} job(s) rewritten, logged, and notified.")


if __name__ == "__main__":
    main()
