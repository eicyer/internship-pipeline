import os
from urllib.parse import quote


def tracking_link(apply_link: str) -> str:
    """Wraps apply_link in a click-tracking redirect so that clicking it (from
    Telegram or the Sheet) marks the row Applied before forwarding to the real
    posting. Falls back to the raw apply_link if TRACKING_BASE_URL isn't set,
    so the feature is opt-in and never breaks the pipeline if unconfigured."""
    base = os.environ.get("TRACKING_BASE_URL")
    if not base:
        return apply_link
    return f"{base}?link={quote(apply_link, safe='')}"
