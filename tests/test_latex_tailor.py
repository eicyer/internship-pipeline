"""
Mocked tests for pipeline/latex_tailor.py — no Anthropic API calls, no cost.

Covers:
  - the company whitelist gate (config.LATEX_TAILOR_COMPANIES)
  - the hard daily rewrite cap (MAX_LATEX_REWRITES_PER_DAY / _consume_budget)
  - "changed": false entries produce no LaTeX block
  - the ±2 char length safety net drops an over/under-length rewrite
  - LaTeX block rendering for both "experience" and "project" sections

Run: pytest tests/test_latex_tailor.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import config
from pipeline.fetcher import Job
from pipeline import latex_tailor

EXPERIENCES = [
    {
        "id": "turkish_technology",
        "section": "experience",
        "company": "Turkish Technology (Turkish Airlines Subsidiary)",
        "role": "Software Engineer Intern",
        "location": "Istanbul, Turkey",
        "time": "June 2026 -- July 2026",
        "bullets": [
            "Engineered a secure multi-partner data-sharing API with scoped JWT auth",
            "Built an idempotent ingestion pipeline with a fault-tolerant parsing layer",
        ],
    },
    {
        "id": "cornell_dining_planner",
        "section": "project",
        "company": "Cornell Dining Planner",
        "role": "",
        "location": "",
        "time": "July 2026 -- Present",
        "tech_stack": "FastAPI, PostgreSQL, React Native, Expo, OAuth",
        "bullets": [
            "Built a personalization engine feeding an optimizer for macro targets",
        ],
    },
    {
        "id": "tubitak",
        "section": "experience",
        "company": "TUBITAK",
        "role": "Machine Learning Intern",
        "location": "Gebze, Turkey",
        "time": "June 2023 -- July 2023",
        "bullets": ["Engineered 2 PySpark pipelines processing 4 GB of data"],
    },
]


def _job(company="Acme", role="Software Engineer Intern", requirements="Python, JWT auth, React"):
    return Job(
        company=company, role=role, location="Remote",
        apply_link=f"https://acme.com/{company}", requirements=requirements,
    )


def _make_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Every test gets a fresh budget file and an empty whitelist unless it sets one."""
    monkeypatch.setattr(latex_tailor, "_BUDGET_STATE_PATH", tmp_path / "budget.json")
    monkeypatch.setattr(latex_tailor, "OUTPUT_DIR", tmp_path / "tailored_bullets")
    monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", [])
    yield


class TestWhitelistGate:
    @pytest.mark.mock
    def test_no_eligible_experiences_returns_none_without_calling_api(self):
        """config.LATEX_TAILOR_COMPANIES is empty by default — nothing should be sent to Sonnet."""
        with patch.object(latex_tailor, "_get_client") as mock_client:
            result = latex_tailor.tailor_latex_bullets(_job(), EXPERIENCES)
        assert result is None
        mock_client.assert_not_called()

    @pytest.mark.mock
    def test_only_whitelisted_experiences_are_sent(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        response = json.dumps([{"id": "turkish_technology", "changed": False}])

        with patch.object(latex_tailor, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(response)
            latex_tailor.tailor_latex_bullets(_job(), EXPERIENCES)
            prompt = mock_client.return_value.messages.create.call_args.kwargs["messages"][0]["content"]

        assert "turkish_technology" in prompt
        assert "cornell_dining_planner" not in prompt
        assert "tubitak" not in prompt


class TestDailyBudgetCap:
    @pytest.mark.mock
    def test_cap_stops_api_calls_after_max_per_day(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        response = json.dumps([{"id": "turkish_technology", "changed": False}])

        with patch.object(latex_tailor, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(response)
            for i in range(7):
                latex_tailor.tailor_latex_bullets(_job(company=f"Co{i}"), EXPERIENCES, max_per_day=5)

        assert mock_client.return_value.messages.create.call_count == 5, (
            "Budget must hard-stop Sonnet calls at max_per_day regardless of how many jobs are offered."
        )

    @pytest.mark.mock
    def test_cap_persists_across_separate_calls_same_day(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        assert latex_tailor._consume_budget(max_per_day=2) is True
        assert latex_tailor._consume_budget(max_per_day=2) is True
        assert latex_tailor._consume_budget(max_per_day=2) is False, "3rd call same day must be rejected"

    @pytest.mark.mock
    def test_budget_resets_on_a_new_day(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        latex_tailor._save_budget_state({"date": "2020-01-01", "count": 999})
        assert latex_tailor._consume_budget(max_per_day=1) is True, "A stale date must not carry over its count"


class TestChangedFlagAndLengthSafety:
    @pytest.mark.mock
    def test_changed_false_produces_no_file(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        response = json.dumps([{"id": "turkish_technology", "changed": False}])

        with patch.object(latex_tailor, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(response)
            result = latex_tailor.tailor_latex_bullets(_job(), EXPERIENCES)

        assert result is None

    @pytest.mark.mock
    def test_oversized_rewrite_is_dropped(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        too_long = [
            "Engineered a secure multi-partner data-sharing API with scoped JWT auth PLUS TWENTY EXTRA CHARS HERE",
            "Built an idempotent ingestion pipeline with a fault-tolerant parsing layer",
        ]
        response = json.dumps([{"id": "turkish_technology", "changed": True, "bullets": too_long}])

        with patch.object(latex_tailor, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(response)
            result = latex_tailor.tailor_latex_bullets(_job(), EXPERIENCES)

        assert result is None, "A rewrite that blows the ±2 char budget must be dropped, not written"

    @pytest.mark.mock
    def test_valid_rewrite_within_tolerance_is_written(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        original = EXPERIENCES[0]["bullets"]
        within_tolerance = [b[:-1] for b in original]  # 1 char shorter each — within ±2
        response = json.dumps([{"id": "turkish_technology", "changed": True, "bullets": within_tolerance}])

        with patch.object(latex_tailor, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(response)
            result = latex_tailor.tailor_latex_bullets(_job(), EXPERIENCES)

        assert result is not None
        content = open(result).read()
        assert "\\resumeSubheading" in content
        assert within_tolerance[0] in content


class TestLatexRendering:
    @pytest.mark.mock
    def test_experience_block_uses_resumesubheading(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        block = latex_tailor._render_block(EXPERIENCES[0], ["Bullet one", "Bullet two"])
        assert "\\resumeSubheading" in block
        assert "\\resumeItem{Bullet one}" in block
        assert "\\resumeItem{Bullet two}" in block
        assert "Istanbul, Turkey" in block

    @pytest.mark.mock
    def test_project_block_uses_resumeprojectheading(self):
        block = latex_tailor._render_block(EXPERIENCES[1], ["Bullet one"])
        assert "\\resumeProjectHeading" in block
        assert "FastAPI, PostgreSQL, React Native, Expo, OAuth" in block
        assert "\\resumeItem{Bullet one}" in block

    @pytest.mark.mock
    def test_output_file_includes_job_header(self, monkeypatch):
        monkeypatch.setattr(config, "LATEX_TAILOR_COMPANIES", ["turkish_technology"])
        response = json.dumps([{
            "id": "turkish_technology", "changed": True,
            "bullets": [b[:-1] for b in EXPERIENCES[0]["bullets"]],
        }])
        job = _job(company="Stripe", role="Backend Intern")

        with patch.object(latex_tailor, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(response)
            result = latex_tailor.tailor_latex_bullets(job, EXPERIENCES)

        content = open(result).read()
        assert "Stripe" in content
        assert "Backend Intern" in content
        assert job.apply_link in content
