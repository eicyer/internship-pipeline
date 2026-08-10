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

_STATUS_OPTIONS = ["To Apply", "Applied", "Interview / OA", "Offer", "Rejected"]

_COLUMN_WIDTHS = [90, 130, 210, 120, 280, 180, 75, 80, 360, 100]

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


def format_sheet() -> None:
    """Apply one-time visual formatting: frozen header, colors, column widths, conditional rules."""
    svc = _get_service()
    sid = _sheet_id()

    # Resolve the numeric gid for Sheet1
    meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
    gid = meta["sheets"][0]["properties"]["sheetId"]

    def _color(r, g, b):
        return {"red": r / 255, "green": g / 255, "blue": b / 255}

    requests = []

    # Freeze header row
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": gid,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # Header row: dark navy background, white bold text, center-aligned
    requests.append({
        "repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _color(30, 41, 59),
                    "textFormat": {
                        "bold": True,
                        "foregroundColor": _color(248, 250, 252),
                        "fontSize": 10,
                    },
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "CLIP",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    })

    # Default data rows: wrap Bullet Suggestions (col I = index 8), clip everything else
    requests.append({
        "repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 10},
            "cell": {
                "userEnteredFormat": {
                    "verticalAlignment": "TOP",
                    "wrapStrategy": "CLIP",
                }
            },
            "fields": "userEnteredFormat(verticalAlignment,wrapStrategy)",
        }
    })
    requests.append({
        "repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": 8, "endColumnIndex": 9},
            "cell": {
                "userEnteredFormat": {"wrapStrategy": "WRAP"},
            },
            "fields": "userEnteredFormat(wrapStrategy)",
        }
    })

    # Column widths
    for i, px in enumerate(_COLUMN_WIDTHS):
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": gid,
                    "dimension": "COLUMNS",
                    "startIndex": i,
                    "endIndex": i + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })

    # Filter dropdowns on header
    requests.append({
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": gid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 10,
                }
            }
        }
    })

    # Data validation: Status column (J = index 9)
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": gid,
                "startRowIndex": 1,
                "startColumnIndex": 9,
                "endColumnIndex": 10,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": v} for v in _STATUS_OPTIONS],
                },
                "showCustomUi": True,
                "strict": False,
            },
        }
    })

    # Conditional formatting: Fit Score (G = col index 6)
    score_range = {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": 6, "endColumnIndex": 7}
    score_rules = [
        # red: < 7
        ("NUMBER_LESS_THAN", "7", _color(242, 184, 181)),
        # yellow: = 7
        ("NUMBER_EQ", "7", _color(255, 229, 153)),
        # light green: = 8
        ("NUMBER_EQ", "8", _color(183, 225, 205)),
        # green: >= 9
        ("NUMBER_GREATER_THAN_EQ", "9", _color(87, 187, 138)),
    ]
    for i, (ctype, val, bg) in enumerate(score_rules):
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [score_range],
                    "booleanRule": {
                        "condition": {
                            "type": ctype,
                            "values": [{"userEnteredValue": val}],
                        },
                        "format": {"backgroundColor": bg},
                    },
                },
                "index": i,
            }
        })

    # Conditional formatting: Grad Flag YES (H = col index 7) → red
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": gid, "startRowIndex": 1, "startColumnIndex": 7, "endColumnIndex": 8}],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": "YES"}],
                    },
                    "format": {"backgroundColor": _color(242, 184, 181)},
                },
            },
            "index": 4,
        }
    })

    svc.spreadsheets().batchUpdate(
        spreadsheetId=sid, body={"requests": requests}
    ).execute()


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
        format_sheet()


def get_existing_links() -> set:
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range="Sheet1!E:E"
    ).execute()
    rows = result.get("values", [])
    return {row[0] for row in rows[1:] if row}  # skip header


def get_existing_keys() -> set:
    """Normalized company|role identity keys for every row already logged, for cross-link dedup."""
    from pipeline.fetcher import normalize_key

    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range="Sheet1!B:C"
    ).execute()
    rows = result.get("values", [])
    keys = set()
    for row in rows[1:]:  # skip header
        if len(row) >= 2:
            keys.add(normalize_key(row[0], row[1]))
    return keys


def _format_bullets_for_sheet(analysis: dict) -> str:
    ranked = analysis.get("ranked_experiences", [])
    parts = []
    exp_num = 0
    for exp in ranked:
        bullets = exp.get("optimized_bullets", [])
        if not bullets:
            continue
        exp_num += 1
        parts.append(f"[{exp['company']} → #{exp_num}]")
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
