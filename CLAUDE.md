# Internship Pipeline

Automated daily pipeline that fetches new internship listings from public GitHub repos, filters them, scores them against the candidate's skills, and rewrites resume bullet points for top matches. Runs on GitHub Actions cron and outputs to Google Sheets + Telegram.

## How to test locally

```bash
MAX_JOBS_PER_REPO=7 python main.py
```

`MAX_JOBS_PER_REPO=7` caps each of the 4 repos to 7 rows (~28 jobs total) so you don't burn API credits or flood Sheets during development. Leave it unset in production — the cron only sees the delta anyway.

All secrets (`ANTHROPIC_API_KEY`, `GOOGLE_SHEETS_CREDS`, `GOOGLE_SHEET_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GH_PAT`) must be set as environment variables locally. `TRACKING_BASE_URL` is optional (see "Click-to-apply tracking" below) — the pipeline runs fine without it, it just skips the auto-Applied behavior.

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

Jobs are deduped on two independent signals, since the same posting is often listed by multiple source repos under different apply URLs (referral link vs. direct company link):
1. **`apply_link`** — exact URL match.
2. **`dedup_key`** (`pipeline/fetcher.py::normalize_key`) — normalized `company|role`. If the role matches a recognized family (see `pipeline/role_families.py`), the key uses the family name instead of the literal title, so e.g. "Software Engineer Intern" and "SWE Intern - DV Commodities" from the same company collapse into one slot — one job per company per role-family. Roles that don't match any family (shouldn't happen for anything reaching this stage, since Stage 1 already rejects them) fall back to the cleaned literal title. Same company with a *different* family, or a different company with the *same* family, are not considered duplicates.

Both signals are checked at three layers:
1. Within a single run, across the 4 source repos (`fetch_new_jobs` in `pipeline/fetcher.py`).
2. `data/seen_jobs.json` — `{"links": [...], "keys": [...]}`, persisted to the repo after every run (committed by GitHub Actions with `[skip ci]` to avoid triggering the workflow again). The old flat-list-of-links format is still read transparently for backward compatibility.
3. Google Sheets — existing links (col E) and existing company/role pairs (cols B/C, normalized) are pulled at startup and merged in.

If the `seen_jobs.json` push ever fails, the Sheets-based dedup acts as the safety net.

## Stage 1 whitelist

`pipeline/stage1_filter.py` and dedup's `normalize_key` (`pipeline/fetcher.py`) share a single source of truth for recognized roles: `pipeline/role_families.py`. Its `role_family()` classifies a title into one of `software_engineer`, `backend_engineer`, `frontend_engineer`, `mle`, `data_scientist`, `forward_deployed_engineer`, `applied_scientist`, `ai_engineer`, or `intern` (exact matches for `"Intern"` / `"Software Intern"`, anchored with `^$`), or returns `None`.

Stage 1 is a **whitelist** (not blacklist): only roles where `role_family()` returns non-`None` pass. Anything unclassified is rejected — including generic "Engineering Intern", DevOps, PM, Quant, Research Scientist, etc.

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

## Sheet ordering & styling

`append_row()` (`pipeline/sheets.py`) inserts each new job directly under the header row instead of appending at the bottom, so the sheet always reads newest-first. `format_sheet()` applies the visual styling (navy header, alternating row banding, thin borders, conditional color-coding for Status / Fit Score / Grad Flag, column widths) and is idempotent — it clears any conditional format rules / banded ranges it previously created before re-adding them, so it can be safely re-run.

Columns (`HEADER` in `pipeline/sheets.py`): Date Found, Company, Role, Location, Link, Status, Fit Score, Grad Flag, Bullet Suggestions, Skills Match — Skills Match sits rightmost, and Status (a dropdown defaulting to `To Apply`, with values `To Apply`/`Applied`/`OA/Interview`/`Rejected` color-coded yellow/green/blue/red) takes the column it used to occupy.

To reorder rows logged before this change (which were appended oldest-first) and refresh their styling, run `python scripts/refresh_sheet.py` once. Don't run it twice — it reverses whatever order is currently in the sheet.

## Click-to-apply tracking

Clicking the apply link — from Telegram's "Apply Now" button or the Sheet's Link column — flips that row's Status from `To Apply` to `Applied` automatically, on the assumption that clicking means you're applying.

There's no persistent server in this pipeline (it only runs on GitHub Actions cron), so the redirect hop is handled by a small Google Apps Script Web App bound to the same Sheet — free, and it can edit the Sheet directly. Source lives in `appscript/click_tracker.gs`; deploy it once by following the comment at the top of that file (paste into Extensions -> Apps Script on the Sheet, set `SPREADSHEET_ID`, deploy as a Web App, "Execute as: Me" / "Who has access: Anyone"), then set the deployment's `/exec` URL as `TRACKING_BASE_URL`.

How it's wired on the Python side:
- `pipeline/tracking.py::tracking_link(apply_link)` wraps a raw apply link as `{TRACKING_BASE_URL}?link={apply_link}`. If `TRACKING_BASE_URL` isn't set, it returns the raw link unchanged — the feature is opt-in and never breaks the pipeline.
- `notifier.py` uses `tracking_link()` for the Telegram "Apply Now" URL.
- `sheets.py::append_row()` keeps the Link cell's underlying text value as the raw `apply_link` (since `get_existing_links()` dedups on that raw text) but attaches the tracking URL as a rich-text hyperlink override (`userEnteredFormat.textFormat.link`), so clicking the cell in Sheets goes through the tracker while the dedup logic is untouched.

The Apps Script only flips Status if it's still `To Apply` — clicking an already-`Applied`/`Rejected`/etc. row's link won't stomp on a status you've since changed by hand.
