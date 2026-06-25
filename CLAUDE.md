# Internship Pipeline

Automated daily pipeline that fetches new internship listings from public GitHub repos, filters them, scores them against the candidate's skills, and rewrites resume bullet points for top matches. Runs on GitHub Actions cron and outputs to Google Sheets + Telegram.

## How to test locally

```bash
MAX_JOBS_PER_REPO=7 python main.py
```

`MAX_JOBS_PER_REPO=7` caps each of the 4 repos to 7 rows (~28 jobs total) so you don't burn API credits or flood Sheets during development. Leave it unset in production — the cron only sees the delta anyway.

All secrets (`ANTHROPIC_API_KEY`, `GOOGLE_SHEETS_CREDS`, `GOOGLE_SHEET_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GH_PAT`) must be set as environment variables locally.

## Pipeline flow

```
fetch_new_jobs()          4 GitHub repos → deduplicated Job objects
       ↓
keyword_filter()          Stage 1: whitelist filter — hardcoded Python, no API calls
       ↓
fetch_all_requirements()  parallel scrape of job posting pages (Workday CXS → Jina fallback)
       ↓
haiku_score()             Stage 2a: cheap fit scoring (Haiku) for every Stage 1 passer
       ↓
FIT_SCORE_THRESHOLD gate  jobs below 7/10 OR with grad_flag are dropped here
       ↓
sonnet_rewrite()          Stage 2b: Sonnet selects top 3 experiences and rewrites bullets
       ↓
append_row() + send_telegram()    Google Sheets + Telegram notification
```

Target volume: ~20 jobs/week reach Sonnet rewriting.

## Key tuning lever

`FIT_SCORE_THRESHOLD = 7` in `main.py`. Raise to 8 if too many jobs are getting through; lower to 6 if too few. This is the primary volume control for Sonnet spend.

## Deduplication

Two-layer dedup to avoid reprocessing jobs across daily runs:
1. `data/seen_jobs.json` — persisted to the repo after every run (committed by GitHub Actions with `[skip ci]` to avoid triggering the workflow again)
2. Google Sheets existing links — pulled at startup and merged into `seen`

If the `seen_jobs.json` push ever fails, the Sheets dedup acts as the safety net.

## Stage 1 whitelist

`pipeline/stage1_filter.py` uses `re.search()` against a **whitelist** (not blacklist). Only roles matching an allowed pattern pass. Allowed: software engineer, SWE, SDE, backend/frontend engineer/developer, full-stack, data scientist, ML engineer, MLE, forward deployed engineer, applied scientist, AI engineer, and exact matches for `"Intern"` and `"Software Intern"` (anchored with `^$`).

Anything not in the whitelist is rejected — including generic "Engineering Intern", DevOps, PM, Quant, Research Scientist, etc.

## Updating the resume

Edit `config.py` — it's the single source of truth for both `SKILLS` (used in Haiku scoring prompt) and `EXPERIENCES` (used in both Haiku ranking and Sonnet rewriting). No other file needs to change when the resume changes.

Each experience needs: `company`, `role`, `time`, `skills` (buzzword list for Haiku), `bullets` (full text for Sonnet).

## Source repos

Four community-maintained GitHub repos are scraped via the GitHub Contents API (authenticated with `GH_PAT`):
- `SimplifyJobs/Summer2026-Internships` — HTML table format
- `speedyapply/2026-SWE-College-Jobs` — markdown table
- `zapplyjobs/Internships-2026` — markdown table
- `vanshb03/Summer2027-Internships` — markdown table (2027 listings; Haiku sets `grad_flag=true` if 2028 grad required)

## Model choices

- **Haiku** (`claude-haiku-4-5-20251001`): Stage 2a scoring. Runs on every Stage 1 passer. Cheap (~250 tokens in, ~80 out). Returns `fit_score`, `skills_matched`, `grad_flag`, `top_indices`.
- **Sonnet** (`claude-sonnet-4-6`): Stage 2b rewriting. Only runs on jobs that clear `FIT_SCORE_THRESHOLD`. Selects the 3 most relevant experiences from the full list and rewrites 2 bullets each. More expensive — gate exists to limit how often it runs.

## Requirements fetching

`pipeline/requirements_fetcher.py` runs in parallel (6 threads) before Stage 2. For Workday URLs it hits the unauthenticated CXS JSON API directly; for everything else it falls back to Jina Reader (free, 200 req/day limit). If fetching fails, `job.requirements` is `""` and Stage 2 falls back to role-title-only mode — this is handled gracefully, not an error.

## Output shape

`sheets.py` and `notifier.py` both expect `analysis` dict with keys: `fit_score`, `skills_matched`, `grad_flag`, `ranked_experiences`. The `ranked_experiences` list has the 3 rewritten experiences first (with `optimized_bullets`), then the rest appended with empty bullets.
