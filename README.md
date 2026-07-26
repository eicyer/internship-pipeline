# Internship Pipeline

Daily GitHub Actions cron that finds new SWE internship listings, filters and scores them against your resume, rewrites bullet points for the best matches, and posts them to Google Sheets + Telegram.

```
fetch_new_jobs()  →  keyword_filter()  →  fetch_all_requirements()
     →  haiku_score()  →  FIT_SCORE_THRESHOLD gate  →  sonnet_rewrite()
     →  Google Sheets + Telegram
```

## Sources

- [`SimplifyJobs/Summer2026-Internships`](https://github.com/SimplifyJobs/Summer2026-Internships)
- [`speedyapply/2026-SWE-College-Jobs`](https://github.com/speedyapply/2026-SWE-College-Jobs)
- [`zapplyjobs/Internships-2026`](https://github.com/zapplyjobs/Internships-2026)
- [`vanshb03/Summer2027-Internships`](https://github.com/vanshb03/Summer2027-Internships)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GH_PAT, ANTHROPIC_API_KEY, GOOGLE_SHEETS_CREDS,
                        # GOOGLE_SHEET_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

## Run

```bash
MAX_JOBS_PER_REPO=7 python main.py   # capped dev run; unset for production
```

## Configuration

- `main.py` — `FIT_SCORE_THRESHOLD` (default `7`) controls how many jobs reach Sonnet rewriting.
- `config.py` — single source of truth for `SKILLS` and `EXPERIENCES`; edit here when your resume changes.

## Dedup

`data/seen_jobs.json` (committed after every run) plus existing Sheets links as a fallback.

See `CLAUDE.md` for full architecture details.
