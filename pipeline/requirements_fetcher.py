import html as html_module
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

TIMEOUT = 10
MAX_CHARS = 800

_SECTION_RE = re.compile(
    r"(?:minimum |basic |required |preferred |key )?"
    r"(?:qualifications?|requirements?|what you(?:'ll| will) (?:need|bring|have)|"
    r"must[- ]have|nice[- ]to[- ]have|what we(?:'re| are) looking for|"
    r"you(?:'re| are)(?: a)? (?:fit|match|great fit) if|"
    r"skills?(?: required| needed| we(?:'re| are) looking for)?)",
    re.IGNORECASE,
)


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_section(text: str) -> str:
    """Return up to MAX_CHARS starting at the first requirements-like header."""
    m = _SECTION_RE.search(text)
    start = m.start() if m else max(0, len(text) // 3)
    return text[start : start + MAX_CHARS].strip()


def _fetch_workday(url: str) -> str | None:
    """
    Hit Workday's public unauthenticated CXS JSON API directly.
    No login, no headless browser needed.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    m = re.match(r"^(.+?)\.(wd\d+)\.myworkdayjobs\.com$", host)
    if not m:
        return None

    tenant = m.group(1)
    parts = parsed.path.split("/job/", 1)
    if len(parts) != 2:
        return None

    site = parts[0].strip("/").split("/")[-1]
    job_path = parts[1]
    cxs_url = f"https://{host}/wday/cxs/{tenant}/{site}/job/{job_path}"

    try:
        resp = requests.get(
            cxs_url,
            timeout=TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if not resp.ok:
            return None
        data = resp.json()
        info = data.get("jobPostingInfo", {})
        desc_html = info.get("jobDescription", "") or info.get("additionalJobDescription", "")
        if not desc_html:
            return None
        return _extract_section(_strip_html(desc_html))
    except Exception:
        return None


def _fetch_jina(url: str) -> str | None:
    """Fetch any job page as clean markdown via Jina Reader (free, 200 req/day)."""
    try:
        resp = requests.get(
            f"https://r.jina.ai/{url}",
            timeout=TIMEOUT,
            headers={"Accept": "text/plain"},
        )
        if not resp.ok:
            return None
        return _extract_section(resp.text)
    except Exception:
        return None


def fetch_requirements(url: str) -> str:
    """
    Returns a requirements snippet (≤800 chars) for the given job URL.
    - myworkdayjobs.com: tries CXS API first, falls back to Jina
    - everything else: Jina only
    - any failure: returns "" so Stage 2 falls back to role-title-only mode
    """
    if "myworkdayjobs.com" in url:
        result = _fetch_workday(url)
        if result:
            return result
    return _fetch_jina(url) or ""


def fetch_all_requirements(jobs_with_flags: list[tuple]) -> None:
    """
    Parallel fetch for all passing jobs. Mutates job.requirements in-place.
    Uses up to 6 threads to keep total fetch time under ~30s for 25 jobs.
    """
    def _fetch_one(item):
        job, _ = item
        job.requirements = fetch_requirements(job.apply_link)
        return job

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_one, item): item[0] for item in jobs_with_flags}
        for future in as_completed(futures):
            job = futures[future]
            status = f"{len(job.requirements)} chars" if job.requirements else "not found"
            print(f"  {job.company}: requirements {status}")
