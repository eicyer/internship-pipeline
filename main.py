import json
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

STATE_FILE = "data/seen_jobs.json"

_max = os.getenv("MAX_JOBS_PER_REPO")
MAX_JOBS_PER_REPO: int | None = int(_max) if _max else None

FIT_SCORE_THRESHOLD = 7


def load_seen() -> tuple[set, set]:
    """Returns (seen_links, seen_keys). Handles the legacy flat-list-of-links format."""
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), set()

    if isinstance(data, list):  # legacy format: flat list of links
        return set(data), set()
    return set(data.get("links", [])), set(data.get("keys", []))


def save_seen(links: set, keys: set) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump({"links": sorted(links), "keys": sorted(keys)}, f, indent=2)


def main() -> None:
    from pipeline.fetcher import fetch_new_jobs
    from pipeline.resume_parser import parse_resume
    from pipeline.stage1_filter import keyword_filter
    from pipeline.requirements_fetcher import fetch_all_requirements
    from pipeline.stage2_analysis import haiku_score, sonnet_rewrite
    from pipeline.sheets import ensure_header, get_existing_links, get_existing_keys, append_row, get_sheet_url
    from pipeline.notifier import send_telegram, send_run_summary

    if MAX_JOBS_PER_REPO:
        log.info(f"Dev mode: capping each repo to {MAX_JOBS_PER_REPO} rows (~{MAX_JOBS_PER_REPO * 4} total)")

    seen_links, seen_keys = load_seen()

    try:
        seen_links |= get_existing_links()
        seen_keys |= get_existing_keys()
    except Exception as e:
        log.warning(f"Could not fetch existing sheet links/keys (continuing): {e}")

    log.info(f"Loaded {len(seen_links)} already-seen job links, {len(seen_keys)} known company/role keys")

    skills_str, experiences = parse_resume()
    log.info(f"Resume: {len(experiences)} experiences | skills: {skills_str}")

    new_jobs = fetch_new_jobs(seen_links, seen_keys, per_repo=MAX_JOBS_PER_REPO)
    if not new_jobs:
        log.info("No new jobs found. Done.")
        save_seen(seen_links, seen_keys)
        send_run_summary({"new_jobs": 0, "stage1": 0, "scored": 0, "above_threshold": 0, "logged": 0})
        return

    # Stage 1: whitelist filter
    passing = keyword_filter(new_jobs)

    stats = {
        "new_jobs": len(new_jobs),
        "stage1": len(passing),
        "scored": 0,
        "above_threshold": 0,
        "logged": 0,
        "dropped_low_fit": 0,
        "dropped_grad_flag": 0,
        "dropped_both": 0,
    }

    if not passing:
        log.info("No matches after Stage 1.")
        save_seen(seen_links | {j.apply_link for j in new_jobs}, seen_keys | {j.dedup_key for j in new_jobs})
        send_run_summary(stats)
        return

    log.info(f"Fetching requirements for {len(passing)} jobs (parallel)...")
    fetch_all_requirements(passing)

    ensure_header()

    # Stage 2a: Haiku scores every Stage 1 passer
    log.info(f"Stage 2a: Haiku scoring {len(passing)} jobs...")
    scored = []
    for job, grad_flag_hint in passing:
        log.info(f"  Scoring: {job.company} — {job.role}")
        score = haiku_score(job, skills_str, experiences, grad_flag_hint)
        scored.append((job, score))
        log.info(f"    fit={score['fit_score']}/10  skills={score['skills_matched']}  grad_flag={score['grad_flag']}")

    stats["scored"] = len(scored)

    above_threshold = [
        (job, score) for job, score in scored
        if score["fit_score"] >= FIT_SCORE_THRESHOLD and not score["grad_flag"]
    ]
    below_threshold = [
        (job, score) for job, score in scored
        if score["fit_score"] < FIT_SCORE_THRESHOLD or score["grad_flag"]
    ]

    stats["above_threshold"] = len(above_threshold)

    for job, score in below_threshold:
        low = score["fit_score"] < FIT_SCORE_THRESHOLD
        grad = score["grad_flag"]
        if low and grad:
            stats["dropped_both"] += 1
        elif grad:
            stats["dropped_grad_flag"] += 1
        else:
            stats["dropped_low_fit"] += 1

    log.info(
        f"Stage 2 gate (fit ≥ {FIT_SCORE_THRESHOLD}, no grad flag): "
        f"{len(scored)} scored → {len(above_threshold)} advance, {len(below_threshold)} dropped"
    )
    for job, score in below_threshold:
        reason = "grad flag" if score["grad_flag"] else f"fit={score['fit_score']}"
        log.info(f"  Dropped ({reason}): {job.company} — {job.role}")

    if not above_threshold:
        log.info("No jobs cleared the threshold. Done.")
        save_seen(seen_links | {j.apply_link for j in new_jobs}, seen_keys | {j.dedup_key for j in new_jobs})
        send_run_summary(stats)
        return

    # Stage 2b: Sonnet selects top 3 experiences and rewrites bullets
    log.info(f"Stage 2b: Sonnet rewriting {len(above_threshold)} jobs...")
    for job, score in above_threshold:
        log.info(f"  Rewriting: {job.company} — {job.role} (fit={score['fit_score']})")
        rewrite = sonnet_rewrite(job, experiences)
        analysis = {**score, **rewrite}
        row_num = append_row(job, analysis)
        sheet_url = get_sheet_url(row_num)
        send_telegram(job, analysis, sheet_url)
        stats["logged"] += 1

    save_seen(seen_links | {j.apply_link for j in new_jobs}, seen_keys | {j.dedup_key for j in new_jobs})
    log.info(f"Done. {stats['logged']} job(s) rewritten, logged, and notified.")
    send_run_summary(stats)


if __name__ == "__main__":
    main()
