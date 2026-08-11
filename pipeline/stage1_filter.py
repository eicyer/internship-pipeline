from .fetcher import Job
from .role_families import role_family


def keyword_filter(jobs: list[Job]) -> list[tuple[Job, bool]]:
    """
    Strict whitelist: only roles explicitly matching SWE/SDE/MLE/DS/FDE variants pass.
    Rejects anything not in the whitelist (generic "Engineering Intern", PM, DevOps, etc.).
    grad_flag is always False here — Stage 2a Haiku detects it per-job.
    """
    passing, rejected = [], 0
    for job in jobs:
        if role_family(job.role) is not None:
            passing.append((job, False))
        else:
            rejected += 1

    print(f"Stage 1 (whitelist filter): {len(jobs)} → {len(passing)} passed, {rejected} rejected")
    return passing
