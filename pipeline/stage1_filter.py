import re
from .fetcher import Job

# Roles to block — non-software engineering types and non-technical roles.
# Everything NOT matching these passes through (permissive by design).
_REJECT = re.compile(
    r"hardware engineer"
    r"|electrical engineer"
    r"|mechanical engineer"
    r"|civil engineer"
    r"|chemical engineer"
    r"|biomedical engineer"
    r"|aerospace engineer"
    r"|aeronautical"
    r"|structural engineer"
    r"|manufacturing engineer"
    r"|industrial engineer"
    r"|materials engineer"
    r"|process engineer"
    r"|optical engineer"
    r"|photonic"
    r"|network engineer"
    r"|sales(?: engineer| intern| associate| rep)"
    r"|marketing intern"
    r"|human resources"
    r"|\bhr intern"
    r"|supply chain"
    r"|talent acquisition"
    r"|recruiting intern"
    r"|finance intern"
    r"|financial analyst"
    r"|business analyst"
    r"|legal intern"
    r"|graphic design"
    r"|ux designer"
    r"|ui/ux",
    re.IGNORECASE,
)


def keyword_filter(jobs: list[Job]) -> list[tuple[Job, bool]]:
    """
    Pure Python keyword filter replacing the Stage 1 Haiku call.
    Rejects non-software engineering and non-technical roles.
    Accepts SWE, SDE, MLE, DE, DS, backend, frontend, fullstack, AI, and
    anything else that doesn't match the reject list.
    grad_flag is always False here — Stage 2a Haiku detects it per-job
    using the actual requirements text.
    """
    passing, rejected = [], 0
    for job in jobs:
        if _REJECT.search(job.role):
            rejected += 1
        else:
            passing.append((job, False))

    print(f"Stage 1 (keyword filter): {len(jobs)} → {len(passing)} passed, {rejected} rejected")
    return passing
