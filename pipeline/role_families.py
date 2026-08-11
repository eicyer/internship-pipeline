import re

# Ordered (family_name, pattern) pairs. First match wins, so more specific
# families (e.g. mle) are checked before broader ones that could overlap
# (e.g. ai_engineer). This is the single source of truth for recognized role
# categories — used both by Stage 1's whitelist and by dedup's company+role key.
ROLE_FAMILIES = [
    ("software_engineer", re.compile(
        r"software engineer"
        r"|software developer"
        r"|software development engineer"
        r"|\bswe\b"
        r"|\bsde\b"
        r"|full.?stack engineer"
        r"|full.?stack developer",
        re.IGNORECASE,
    )),
    ("backend_engineer", re.compile(
        r"backend engineer"
        r"|backend developer"
        r"|back-end engineer"
        r"|back-end developer",
        re.IGNORECASE,
    )),
    ("frontend_engineer", re.compile(
        r"frontend engineer"
        r"|frontend developer"
        r"|front-end engineer"
        r"|front-end developer",
        re.IGNORECASE,
    )),
    ("mle", re.compile(
        r"machine learning engineer"
        r"|\bml engineer"
        r"|\bmle\b"
        r"|ai/ml engineer"
        r"|ai ml engineer",
        re.IGNORECASE,
    )),
    ("data_scientist", re.compile(r"data scientist", re.IGNORECASE)),
    ("forward_deployed_engineer", re.compile(r"forward deployed engineer", re.IGNORECASE)),
    ("applied_scientist", re.compile(r"applied scientist", re.IGNORECASE)),
    ("ai_engineer", re.compile(r"\bai engineer", re.IGNORECASE)),
    ("intern", re.compile(r"^\s*intern\s*$|^\s*software intern\s*$", re.IGNORECASE)),
]


def role_family(role: str) -> str | None:
    """Classify a role title into a recognized family, or None if it matches none."""
    for name, pattern in ROLE_FAMILIES:
        if pattern.search(role):
            return name
    return None
