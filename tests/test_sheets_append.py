"""
append_row() must stay within the Sheets 60-writes/min quota: one batchUpdate per
job, retried with backoff on 429. Fully mocked — no Sheets API calls.

Run: pytest tests/test_sheets_append.py -v
"""

from unittest.mock import MagicMock, patch

import httplib2
import pytest
from googleapiclient.errors import HttpError

from pipeline import sheets
from pipeline.fetcher import Job

pytestmark = pytest.mark.mock


def _job():
    return Job(
        company="Acme",
        role="Software Engineer Intern",
        location="Remote",
        apply_link="https://acme.com/jobs/1",
        source_repo="test/repo",
    )


def _analysis():
    return {
        "fit_score": 8,
        "skills_matched": ["Python", "SQL"],
        "grad_flag": False,
        "ranked_experiences": [],
    }


def _http_error(status):
    return HttpError(httplib2.Response({"status": status}), b"quota exceeded")


@pytest.fixture
def svc(monkeypatch):
    svc = MagicMock()
    monkeypatch.setattr(sheets, "_get_service", lambda: svc)
    monkeypatch.setattr(sheets, "_sheet_id", lambda: "sheet123")
    monkeypatch.setattr(sheets, "_get_gid", lambda: 0)
    monkeypatch.setenv("TRACKING_BASE_URL", "https://track.example/exec")
    return svc


def test_append_row_is_a_single_write(svc):
    assert sheets.append_row(_job(), _analysis()) == 2

    batch = svc.spreadsheets.return_value.batchUpdate
    assert batch.call_count == 1
    assert batch.return_value.execute.call_count == 1
    svc.spreadsheets.return_value.values.return_value.update.assert_not_called()

    reqs = batch.call_args.kwargs["body"]["requests"]
    assert reqs[0]["insertDimension"]["range"] == {
        "sheetId": 0, "dimension": "ROWS", "startIndex": 1, "endIndex": 2,
    }

    update = reqs[1]["updateCells"]
    assert update["range"]["startRowIndex"] == 1 and update["range"]["endRowIndex"] == 2
    cells = update["rows"][0]["values"]
    assert len(cells) == len(sheets.HEADER)
    values = [next(iter(c["userEnteredValue"].values())) for c in cells]
    assert values[1:] == [
        "Acme", "Software Engineer Intern", "Remote", "https://acme.com/jobs/1",
        "To Apply", 8, "NO", "", "Python, SQL",
    ]
    assert cells[6]["userEnteredValue"] == {"numberValue": 8}
    # Link cell keeps the raw link as its value (dedup) but clicks through the tracker
    assert cells[4]["userEnteredValue"] == {"stringValue": "https://acme.com/jobs/1"}
    assert cells[4]["userEnteredFormat"]["textFormat"]["link"]["uri"].startswith(
        "https://track.example/exec?link="
    )


def test_append_row_retries_on_rate_limit(svc):
    execute = svc.spreadsheets.return_value.batchUpdate.return_value.execute
    execute.side_effect = [_http_error(429), _http_error(429), {}]

    with patch.object(sheets.time, "sleep") as sleep:
        assert sheets.append_row(_job(), _analysis()) == 2

    assert execute.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [2, 4]


def test_append_row_gives_up_after_retries(svc):
    execute = svc.spreadsheets.return_value.batchUpdate.return_value.execute
    execute.side_effect = _http_error(429)

    with patch.object(sheets.time, "sleep"), pytest.raises(HttpError):
        sheets.append_row(_job(), _analysis())

    assert execute.call_count == 6


def test_non_retryable_error_raises_immediately(svc):
    execute = svc.spreadsheets.return_value.batchUpdate.return_value.execute
    execute.side_effect = _http_error(400)

    with patch.object(sheets.time, "sleep") as sleep, pytest.raises(HttpError):
        sheets.append_row(_job(), _analysis())

    assert execute.call_count == 1
    sleep.assert_not_called()
