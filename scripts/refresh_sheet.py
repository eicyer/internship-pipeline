"""One-time maintenance: reverse existing rows to newest-first order and
re-apply the sheet's visual formatting (banding, borders, colors) to the
whole sheet, including rows logged before this change.

Usage:
    python scripts/refresh_sheet.py

Requires GOOGLE_SHEETS_CREDS and GOOGLE_SHEET_ID to be set, same as main.py.
Safe to run once. Running it a second time will re-reverse row order, so
don't re-run it after the sheet already reads newest-first.
"""
from pipeline.sheets import format_sheet, reorder_rows_newest_first


def main() -> None:
    n = reorder_rows_newest_first()
    print(f"Reordered {n} existing row(s) to newest-first.")
    format_sheet()
    print("Re-applied visual formatting (banding, borders, colors) to the sheet.")


if __name__ == "__main__":
    main()
