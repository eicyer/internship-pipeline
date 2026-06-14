import json
import os

STATE_FILE = "data/seen_jobs.json"

# Set MAX_JOBS_PER_REPO=7 locally when testing (~28 jobs total across 4 repos).
# Leave unset in production — the daily cron only sees the delta anyway.
_max = os.getenv("MAX_JOBS_PER_REPO")
MAX_JOBS_PER_REPO: int | None = int(_max) if _max else None


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
    from pipeline.stage2_analysis import sonnet_analyze
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

    passing = keyword_filter(new_jobs)

    if not passing:
        print("No matches after Stage 1.")
        save_seen(seen | {j.apply_link for j in new_jobs})
        return

    print(f"\nFetching requirements for {len(passing)} jobs (parallel)...")
    fetch_all_requirements(passing)

    ensure_header()

    print(f"\nRunning Stage 2 analysis (Sonnet) on {len(passing)} jobs...")
    for job, grad_flag_hint in passing:
        print(f"  Analyzing: {job.company} — {job.role}")
        analysis = sonnet_analyze(job, skills_str, experiences, grad_flag_hint)
        row_num = append_row(job, analysis)
        sheet_url = get_sheet_url(row_num)
        send_telegram(job, analysis, sheet_url)

    save_seen(seen | {j.apply_link for j in new_jobs})
    print(f"\nDone. {len(passing)} job(s) logged and notified.")


if __name__ == "__main__":
    main()
