"""One-time maintenance: reverse existing rows to newest-first order and
re-apply the sheet's visual formatting (banding, borders, colors) to the
whole sheet, including rows logged before this change.

Usage:
    python scripts/refresh_sheet.py

Requires GOOGLE_SHEETS_CREDS and GOOGLE_SHEET_ID to be set, same as main.py.

Note: an earlier run of this script got its row order flipped back to
oldest-first by an accidental re-run of a stale (pre-fix) workflow run,
so the reorder step below is temporarily back in. Once this run
completes, remove the reorder_rows_newest_first() call again (see git
history) so a future re-run can't flip it back a second time.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.sheets import format_sheet, reorder_rows_newest_first


def main() -> None:
    n = reorder_rows_newest_first()
    print(f"Reordered {n} existing row(s) to newest-first.")
    format_sheet()
    print("Re-applied visual formatting (banding, borders, colors) to the sheet.")


if __name__ == "__main__":
    main()
