import base64
import html
import json
import os
import re
from dataclasses import dataclass

import requests

REPOS = [
    {
        "slug": "SimplifyJobs/Summer2026-Internships",
        "format": "html_table",
        "col_map": {"company": 0, "role": 1, "location": 2, "link": 3},
    },
    {
        "slug": "speedyapply/2026-SWE-College-Jobs",
        "format": "md_table",
        "col_map": {"company": 0, "role": 1, "location": 2, "link": 4},
    },
    {
        "slug": "zapplyjobs/Internships-2026",
        "format": "md_table",
        "col_map": {"company": 0, "role": 1, "location": 2, "link": 5},
    },
    {
        "slug": "vanshb03/Summer2027-Internships",
        "format": "md_table",
        "col_map": {"company": 0, "role": 1, "location": 2, "link": 3},
    },
]


@dataclass
class Job:
    company: str
    role: str
    location: str
    apply_link: str
    notes: str = ""
    source_repo: str = ""
    requirements: str = ""


def _gh_headers() -> dict:
    pat = os.environ.get("GH_PAT", "")
    headers = {"Accept": "application/vnd.github+json"}
    if pat:
        headers["Authorization"] = f"Bearer {pat}"
    return headers


def _fetch_readme(slug: str) -> str:
    url = f"https://api.github.com/repos/{slug}/contents/README.md"
    resp = requests.get(url, headers=_gh_headers(), timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8")


def _extract_href(cell: str) -> str:
    """Return first non-Simplify-referral href found in cell HTML."""
    urls = re.findall(r'href="([^"]+)"', cell)
    for url in urls:
        if "simplify.jobs/p/" not in url:
            return url
    return urls[0] if urls else ""


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean)
    clean = re.sub(r"\*+", "", clean)         # strip markdown bold
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)  # [text](url) → text
    return clean.strip()


def _parse_html_table(content: str, col_map: dict, slug: str) -> list[Job]:
    """Parse repos that use <table><tr><td> format (SimplifyJobs)."""
    jobs = []
    # Split into rows
    rows = re.split(r"<tr[^>]*>", content)
    last_company = ""
    for row in rows[1:]:  # skip content before first <tr>
        cells = re.split(r"<td[^>]*>", row)
        if len(cells) < 4:
            continue
        raw_company = cells[col_map["company"] + 1]
        raw_role = cells[col_map["role"] + 1]
        raw_location = cells[col_map["location"] + 1]
        raw_link = cells[col_map["link"] + 1]

        company = _strip_html(raw_company)
        role = _strip_html(raw_role)
        location = _strip_html(raw_location)
        apply_link = _extract_href(raw_link)

        if company == "↳":
            company = last_company
        elif company:
            last_company = company

        if not apply_link or not role:
            continue
        jobs.append(Job(company=company, role=role, location=location,
                        apply_link=apply_link, source_repo=slug))
    return jobs


def _parse_md_table(content: str, col_map: dict, slug: str) -> list[Job]:
    """Parse repos that use markdown | pipe | tables with HTML inside cells."""
    jobs = []
    last_company = ""
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[\s\-|]+\|$", line):  # separator row
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        min_cols = max(col_map.values()) + 1
        if len(cells) < min_cols:
            continue

        company = _strip_html(cells[col_map["company"]])
        role = _strip_html(cells[col_map["role"]])
        location = _strip_html(cells[col_map["location"]])

        link_cell = cells[col_map["link"]]
        apply_link = _extract_href(link_cell)
        if not apply_link:
            # try markdown [text](url) format
            m = re.search(r"\(([^)]+)\)", link_cell)
            if m:
                apply_link = m.group(1)

        if company in ("Company", ""):
            continue  # header row
        if company == "↳":
            company = last_company
        elif company:
            last_company = company

        if not apply_link or not role:
            continue
        jobs.append(Job(company=company, role=role, location=location,
                        apply_link=apply_link, source_repo=slug))
    return jobs


def fetch_new_jobs(seen_links: set, per_repo: int | None = None) -> list[Job]:
    """
    Fetch new jobs from all repos.
    per_repo: if set, take only the first N rows per repo (newest-first).
              Leave as None in production to get full delta.
              Set to ~7 during testing to cap total at ~28 jobs.
    """
    all_jobs = []
    for repo in REPOS:
        try:
            content = _fetch_readme(repo["slug"])
            if repo["format"] == "html_table":
                jobs = _parse_html_table(content, repo["col_map"], repo["slug"])
            else:
                jobs = _parse_md_table(content, repo["col_map"], repo["slug"])
            if per_repo is not None:
                jobs = jobs[:per_repo]
            new = [j for j in jobs if j.apply_link not in seen_links]
            print(f"{repo['slug']}: {len(jobs)} scanned, {len(new)} new")
            all_jobs.extend(new)
        except Exception as e:
            print(f"ERROR fetching {repo['slug']}: {e}")
    return all_jobs
