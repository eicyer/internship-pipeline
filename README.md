# Internship Pipeline

Automated daily pipeline that finds new software internship listings, filters them, scores them against your resume, and rewrites bullet points for the best matches — then logs everything to Google Sheets and pings you on Telegram.

## Pipeline flow

```
fetch_new_jobs()          4 GitHub repos → deduplicated Job objects
       ↓
keyword_filter()          Stage 1: whitelist filter (SWE / SDE / MLE / etc.)
       ↓
fetch_all_requirements()  parallel scrape of job posting pages
       ↓
haiku_score()              Stage 2a: cheap fit scoring (Haiku)
       ↓
FIT_SCORE_THRESHOLD gate  drop jobs below 7/10 or flagged as grad-only
       ↓
sonnet_rewrite()           Stage 2b: rewrite resume bullets for top matches (Sonnet)
       ↓
Google Sheets + Telegram
```

Runs on a GitHub Actions cron once a day (~9–10 AM ET) and targets ~20 jobs/week reaching the rewriting stage.

## Sources

Scraped via the GitHub Contents API:
- [`SimplifyJobs/Summer2026-Internships`](https://github.com/SimplifyJobs/Summer2026-Internships)
- [`speedyapply/2026-SWE-College-Jobs`](https://github.com/speedyapply/2026-SWE-College-Jobs)
- [`zapplyjobs/Internships-2026`](https://github.com/zapplyjobs/Internships-2026)
- [`vanshb03/Summer2027-Internships`](https://github.com/vanshb03/Summer2027-Internships)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in secrets, then export them
```

Required environment variables:

| Variable | Purpose |
|---|---|
| `GH_PAT` | GitHub token for reading source repos |
| `ANTHROPIC_API_KEY` | Haiku scoring + Sonnet rewriting |
| `GOOGLE_SHEETS_CREDS` | Service account JSON for Sheets output |
| `GOOGLE_SHEET_ID` | Target spreadsheet |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Run notifications |

## Running locally

```bash
MAX_JOBS_PER_REPO=7 python main.py
```

`MAX_JOBS_PER_REPO` caps each source repo's rows so local runs don't burn API credits or flood Sheets. Leave it unset in production.

## Configuration

- `main.py` — `FIT_SCORE_THRESHOLD` (default `7`) is the main volume/spend control. Raise it to let fewer jobs through to Sonnet, lower it to let more through.
- `config.py` — single source of truth for your `SKILLS` and `EXPERIENCES`. Update this when your resume changes; no other file needs to change.

## Deduplication

Two layers prevent reprocessing the same job:
1. `data/seen_jobs.json`, committed back to the repo after each run
2. Existing links already in the Google Sheet, pulled at startup as a safety net

## Tests

```bash
python -m pytest tests/ -v
```

See `CLAUDE.md` for architecture details, model choices, and internals.
