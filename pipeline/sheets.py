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
_gid = None


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


def _get_gid() -> int:
    """Numeric sheetId (gid) of Sheet1, cached for the process lifetime."""
    global _gid
    if _gid is None:
        svc = _get_service()
        meta = svc.spreadsheets().get(spreadsheetId=_sheet_id()).execute()
        _gid = meta["sheets"][0]["properties"]["sheetId"]
    return _gid


def format_sheet() -> None:
    """Apply visual formatting: frozen header, colors, banding, borders, column widths,
    conditional rules. Safe to call more than once — clears any conditional format
    rules / banded ranges it previously created before re-adding them, so it can be
    re-run to refresh formatting on a sheet that already has data (e.g. after a
    style change) without piling up duplicate rules."""
    svc = _get_service()
    sid = _sheet_id()
    gid = _get_gid()

    def _color(r, g, b):
        return {"red": r / 255, "green": g / 255, "blue": b / 255}

    requests = []

    # Clear any previously-added conditional format rules and banded ranges on
    # this sheet so re-running this function doesn't stack duplicates.
    meta = svc.spreadsheets().get(
        spreadsheetId=sid, fields="sheets(properties(sheetId),conditionalFormats,bandedRanges)"
    ).execute()
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["sheetId"] != gid:
            continue
        num_rules = len(sheet.get("conditionalFormats", []))
        for i in reversed(range(num_rules)):
            requests.append({"deleteConditionalFormatRule": {"sheetId": gid, "index": i}})
        for band in sheet.get("bandedRanges", []):
            requests.append({"deleteBanding": {"bandedRangeId": band["bandedRangeId"]}})

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

    # Taller header row so the bold white-on-navy text has breathing room
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": gid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 32},
            "fields": "pixelSize",
        }
    })

    # Alternating row stripes (banding) for readability. Left open-ended so it
    # auto-extends to newly inserted rows; conditional formatting still wins
    # over banding for the Fit Score / Grad Flag cells.
    requests.append({
        "addBanding": {
            "bandedRange": {
                "range": {"sheetId": gid, "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": 10},
                "rowProperties": {
                    "headerColor": _color(30, 41, 59),
                    "firstBandColor": _color(255, 255, 255),
                    "secondBandColor": _color(241, 245, 249),
                },
            }
        }
    })

    # Thin borders around the whole table (buffered a generous number of rows
    # ahead so freshly inserted rows already look bordered without a re-run).
    requests.append({
        "updateBorders": {
            "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 2000, "startColumnIndex": 0, "endColumnIndex": 10},
            "top": {"style": "SOLID", "width": 1, "color": _color(203, 213, 225)},
            "bottom": {"style": "SOLID", "width": 1, "color": _color(203, 213, 225)},
            "left": {"style": "SOLID", "width": 1, "color": _color(203, 213, 225)},
            "right": {"style": "SOLID", "width": 1, "color": _color(203, 213, 225)},
            "innerHorizontal": {"style": "SOLID", "width": 1, "color": _color(226, 232, 240)},
            "innerVertical": {"style": "SOLID", "width": 1, "color": _color(226, 232, 240)},
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
    """Insert one job row directly under the header, so the most recent find is
    always at the top of the sheet. Returns the 1-based row index of the new row
    (always 2, since it lands right below the frozen header)."""
    svc = _get_service()
    sid = _sheet_id()
    gid = _get_gid()
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

    # Push everything down one row, inheriting formatting from the row below
    # (an existing data row) rather than the header above.
    svc.spreadsheets().batchUpdate(
        spreadsheetId=sid,
        body={"requests": [{
            "insertDimension": {
                "range": {"sheetId": gid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
                "inheritFromBefore": False,
            }
        }]},
    ).execute()
    svc.spreadsheets().values().update(
        spreadsheetId=sid,
        range="Sheet1!A2",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()
    return 2


def reorder_rows_newest_first() -> int:
    """One-time migration: reverse the existing data rows (excluding the header)
    so old logs — which were appended oldest-first — read newest-first like new
    rows now do. Safe to run once; running it again just re-reverses the order,
    so don't call it repeatedly. Returns the number of rows reordered."""
    svc = _get_service()
    sid = _sheet_id()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sid, range="Sheet1!A2:J"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return len(rows)

    width = len(HEADER)
    padded = [r + [""] * (width - len(r)) for r in rows]
    padded.reverse()

    svc.spreadsheets().values().update(
        spreadsheetId=sid,
        range=f"Sheet1!A2:J{len(padded) + 1}",
        valueInputOption="RAW",
        body={"values": padded},
    ).execute()
    return len(padded)


def get_sheet_url(row_num: int = 0) -> str:
    sheet_id = _sheet_id()
    base = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    if row_num:
        return f"{base}/edit#gid=0&range=A{row_num}"
    return base
