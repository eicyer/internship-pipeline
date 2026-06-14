import json
import os
from datetime import date

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = [
    "Date Found", "Company", "Role", "Location", "Link",
    "Skills Match", "Fit Score", "Grad Flag", "Bullet Suggestions", "Status",
]

_service = None


def _get_service():
    global _service
    if _service is None:
        creds_json = os.environ["GOOGLE_SHEETS_CREDS"]
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        _service = build("sheets", "v4", credentials=creds)
    return _service


def _sheet_id() -> str:
    return os.environ["GOOGLE_SHEET_ID"]


def ensure_header():
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range="Sheet1!A1:J1"
    ).execute()
    if not result.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=_sheet_id(),
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [HEADER]},
        ).execute()


def get_existing_links() -> set:
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range="Sheet1!E:E"
    ).execute()
    rows = result.get("values", [])
    return {row[0] for row in rows[1:] if row}  # skip header


def _format_bullets_for_sheet(analysis: dict) -> str:
    """Format top 3 ranked experiences with their optimized bullets for the sheet cell."""
    ranked = analysis.get("ranked_experiences", [])
    parts = []
    for exp in ranked:
        bullets = exp.get("optimized_bullets", [])
        if not bullets:
            continue
        parts.append(f"[{exp['company']} → #{len(parts)+1}]")
        for b in bullets:
            parts.append(f"• {b}")
    return "\n".join(parts)


def append_row(job, analysis: dict) -> int:
    """Append one job row. Returns the 1-based row index of the new row."""
    svc = _get_service()
    bullets = _format_bullets_for_sheet(analysis)
    skills = ", ".join(analysis.get("skills_matched", []))
    grad_flag = "YES" if analysis.get("grad_flag") else "NO"
    row = [
        date.today().isoformat(),
        job.company,
        job.role,
        job.location,
        job.apply_link,
        skills,
        analysis.get("fit_score", ""),
        grad_flag,
        bullets,
        "To Apply",
    ]
    result = svc.spreadsheets().values().append(
        spreadsheetId=_sheet_id(),
        range="Sheet1!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    updated_range = result.get("updates", {}).get("updatedRange", "")
    # Parse row number from range like "Sheet1!A5:J5"
    try:
        row_num = int(updated_range.split("!")[1].split(":")[0][1:])
    except (IndexError, ValueError):
        row_num = 0
    return row_num


def get_sheet_url(row_num: int = 0) -> str:
    sheet_id = _sheet_id()
    base = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    if row_num:
        return f"{base}/edit#gid=0&range=A{row_num}"
    return base
