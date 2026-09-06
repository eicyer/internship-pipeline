"""One-time maintenance: re-apply the sheet's visual formatting (banding,
borders, colors) to the whole sheet, including rows logged before this
change.

Usage:
    python scripts/refresh_sheet.py

Requires GOOGLE_SHEETS_CREDS and GOOGLE_SHEET_ID to be set, same as main.py.

Note: this used to also reverse existing rows to newest-first via
reorder_rows_newest_first() — that migration already ran successfully
against the live sheet, so it's been dropped from this script. Re-adding
and re-running it would re-reverse the now-correct row order.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.sheets import format_sheet


def main() -> None:
    format_sheet()
    print("Re-applied visual formatting (banding, borders, colors) to the sheet.")


if __name__ == "__main__":
    main()
