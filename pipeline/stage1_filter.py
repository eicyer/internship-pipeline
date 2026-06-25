import re
from .fetcher import Job

# Strict whitelist: only the specific SWE/data/ML roles we care about pass.
# Everything NOT matching these is rejected.
_ACCEPT = re.compile(
    r"software engineer"
    r"|software developer"
    r"|software development engineer"
    r"|\bswe\b"
    r"|\bsde\b"
    r"|backend engineer"
    r"|backend developer"
    r"|back-end engineer"
    r"|back-end developer"
    r"|frontend engineer"
    r"|frontend developer"
    r"|front-end engineer"
    r"|front-end developer"
    r"|full.?stack engineer"
    r"|full.?stack developer"
    r"|data scientist"
    r"|machine learning engineer"
    r"|\bml engineer"
    r"|\bmle\b"
    r"|forward deployed engineer"
    r"|applied scientist"
    r"|\bai engineer"
    r"|ai/ml engineer"
    r"|ai ml engineer",
    re.IGNORECASE,
)


def keyword_filter(jobs: list[Job]) -> list[tuple[Job, bool]]:
    """
    Strict whitelist: only roles explicitly matching SWE/SDE/MLE/DS/FDE variants pass.
    Rejects anything not in the whitelist (generic "Engineering Intern", PM, DevOps, etc.).
    grad_flag is always False here — Stage 2a Haiku detects it per-job.
    """
    passing, rejected = [], 0
    for job in jobs:
        if _ACCEPT.search(job.role):
            passing.append((job, False))
        else:
            rejected += 1

    print(f"Stage 1 (whitelist filter): {len(jobs)} → {len(passing)} passed, {rejected} rejected")
    return passing
