import json
import os
import sys

STATE_FILE = "data/seen_jobs.json"
RESUME_PATH = "resume.docx"


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
    from pipeline.stage1_filter import haiku_filter
    from pipeline.stage2_analysis import sonnet_analyze
    from pipeline.sheets import ensure_header, get_existing_links, append_row, get_sheet_url
    from pipeline.notifier import send_telegram

    seen = load_seen()

    # Supplement dedup from Sheets (handles first-run / lost state file)
    try:
        sheet_links = get_existing_links()
        seen |= sheet_links
    except Exception as e:
        print(f"Could not fetch existing sheet links (continuing): {e}")

    print(f"Loaded {len(seen)} already-seen job links")

    # Parse resume once
    try:
        skills_str, bullets = parse_resume(RESUME_PATH)
        print(f"Skills extracted: {skills_str[:120]}")
    except Exception as e:
        print(f"Resume parse failed: {e}")
        sys.exit(1)

    new_jobs = fetch_new_jobs(seen)
    if not new_jobs:
        print("No new jobs found. Done.")
        save_seen(seen)
        return

    print(f"\n{len(new_jobs)} new jobs — running Stage 1 filter (Haiku)...")
    passing = haiku_filter(new_jobs, skills_str)

    if not passing:
        print("No matches after Stage 1.")
        save_seen(seen | {j.apply_link for j in new_jobs})
        return

    ensure_header()

    print(f"\n{len(passing)} matches — running Stage 2 analysis (Sonnet)...")
    for job, grad_flag_hint in passing:
        print(f"  Analyzing: {job.company} — {job.role}")
        analysis = sonnet_analyze(job, skills_str, bullets, grad_flag_hint)
        row_num = append_row(job, analysis)
        sheet_url = get_sheet_url(row_num)
        send_telegram(job, analysis, sheet_url)

    # Mark ALL fetched jobs (not just matches) as seen so we don't reprocess them
    save_seen(seen | {j.apply_link for j in new_jobs})
    print(f"\nDone. {len(passing)} job(s) logged and notified.")


if __name__ == "__main__":
    main()
