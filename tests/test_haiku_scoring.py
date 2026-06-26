"""
Diagnostic tests for haiku_score() false positives and false negatives.

Issue #2: requirements[:600] truncation — relevant tech stack may sit after the cutoff,
          leaving Haiku to score against company marketing copy instead.
Issue #3: max_tokens=120 — if the response is ever cut off mid-JSON, the except branch
          returns fit_score=0, silently dropping a potentially great match.
Issue #6: job.requirements == "" — Haiku scores on title + company alone, no tech signal.

Markers
-------
  @pytest.mark.api   — hits the real Anthropic API (costs tokens).  Skip with: pytest -m "not api"
  @pytest.mark.mock  — fully mocked, no API calls, always free to run.

Run all:        pytest tests/test_haiku_scoring.py -v
Run cheap only: pytest tests/test_haiku_scoring.py -v -m "not api"
"""

import json
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from pipeline.fetcher import Job
from pipeline.stage2_analysis import haiku_score

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SKILLS_STR = (
    "Python, JavaScript, React, SQL, Java, Node.js, scikit-learn, pandas, PostgreSQL"
)

EXPERIENCES = [
    {
        "company": "Carriage",
        "role": "Software Developer",
        "skills": ["PostgreSQL", "Node.js", "REST API", "full-stack"],
    },
    {
        "company": "Bearbox",
        "role": "Software Developer",
        "skills": ["React", "Node.js", "state management"],
    },
    {
        "company": "Tournaid",
        "role": "Software Developer",
        "skills": ["Django", "Python", "SQLite", "full-stack", "automation"],
    },
]

# A block of filler text that is 630 chars long.  It mentions Python and ML in
# a marketing context — the kind of intro many job postings use before the real
# requirements appear.
_MARKETING_INTRO = (
    "About us: TechCorp is a leading company at the frontier of artificial intelligence "
    "and machine learning. Our platform is built on modern cloud infrastructure, and our "
    "internal tools use Python extensively for scripting and automation.  We are a "
    "fast-growing startup backed by top-tier investors, and we value engineers who move "
    "fast and think deeply.  Join us to shape the future of AI-powered products.  We "
    "offer competitive compensation, remote-friendly culture, and the chance to work on "
    "hard problems that matter at scale.  Our ML systems process millions of events daily "
    "using Python-based pipelines, and our data science team relies on SQL and pandas for "
    "analytics.  If you love Python, machine learning, and building impactful products, "
    "we want to hear from you.  Apply now!  "
)
assert len(_MARKETING_INTRO) > 600, "intro must exceed the 600-char truncation point"

_EMBEDDED_REQUIREMENTS = (
    "Requirements: 3+ years C++ (embedded/real-time), FPGA programming, VHDL or "
    "SystemVerilog, bare-metal RTOS experience (FreeRTOS/Zephyr), strong assembly "
    "language skills, NO Python or web frameworks required.  Degree in EE or CE preferred."
)

_FULLSTACK_REQUIREMENTS = (
    "Requirements: proficiency in Python and JavaScript, experience with React and "
    "Node.js, SQL/PostgreSQL database design, REST API development, and full-stack "
    "web application delivery.  Bonus: scikit-learn or pandas for internal tooling."
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_response(text: str):
    """Minimal mock of the anthropic messages.create() return value."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ===========================================================================
# ISSUE #3 — max_tokens=120 truncation (mock tests, no API cost)
# ===========================================================================

class TestIssue3JsonTruncation:
    """
    When Haiku's output is cut off before the JSON closes, json.loads() raises
    JSONDecodeError and the fallback returns fit_score=0.  A genuinely great job
    is silently dropped at the Stage 2 gate (threshold = 7).
    """

    @pytest.mark.mock
    def test_truncated_json_returns_zero_score(self):
        """
        Simulate max_tokens being hit mid-response.  The fallback must produce
        fit_score=0, which will cause the job to be dropped regardless of actual fit.
        """
        truncated = '{"fit_score": 9, "skills_matched": ["Python", "React"], "grad_flag": false, "top_ind'

        job = Job(
            company="Stripe",
            role="Software Engineer Intern",
            location="NYC",
            apply_link="https://stripe.com/jobs/1",
            requirements=_FULLSTACK_REQUIREMENTS,
        )

        with patch("pipeline.stage2_analysis._get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(truncated)
            result = haiku_score(job, SKILLS_STR, EXPERIENCES, grad_flag_hint=False)

        assert result["fit_score"] == 0, (
            "Truncated JSON must fall back to fit_score=0 — this job would be "
            "silently dropped even though it's a strong match."
        )
        assert result["skills_matched"] == []
        assert result["top_indices"] == [0, 1, 2]

    @pytest.mark.mock
    def test_verbose_preamble_is_stripped_correctly(self):
        """
        Regression: before the fix, prose before the JSON caused JSONDecodeError → fit_score=0.
        The regex extraction (re.search for the outermost {...}) now recovers the JSON
        correctly regardless of any leading text.
        """
        with_preamble = 'Here is the JSON:\n{"fit_score": 8, "skills_matched": ["Python"], "grad_flag": false, "top_indices": [0, 1, 2]}'

        job = Job(
            company="Figma",
            role="Software Engineer Intern",
            location="SF",
            apply_link="https://figma.com/jobs/1",
            requirements=_FULLSTACK_REQUIREMENTS,
        )

        with patch("pipeline.stage2_analysis._get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(with_preamble)
            result = haiku_score(job, SKILLS_STR, EXPERIENCES, grad_flag_hint=False)

        assert result["fit_score"] == 8, (
            "Regex extraction should recover the JSON object from a prose-prefixed response."
        )
        assert "Python" in result["skills_matched"]

    @pytest.mark.mock
    def test_clean_json_parses_correctly(self):
        """Baseline: a well-formed response must be parsed without hitting the fallback."""
        clean = '{"fit_score": 8, "skills_matched": ["Python", "React"], "grad_flag": false, "top_indices": [0, 2, 1]}'

        job = Job(
            company="Linear",
            role="Software Engineer Intern",
            location="Remote",
            apply_link="https://linear.app/jobs/1",
            requirements=_FULLSTACK_REQUIREMENTS,
        )

        with patch("pipeline.stage2_analysis._get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = _make_response(clean)
            result = haiku_score(job, SKILLS_STR, EXPERIENCES, grad_flag_hint=False)

        assert result["fit_score"] == 8
        assert "Python" in result["skills_matched"]
        assert result["grad_flag"] is False


# ===========================================================================
# ISSUE #2 — requirements[:600] truncation (live API tests)
# ===========================================================================

class TestIssue2RequirementsTruncation:
    """
    The prompt passes job.requirements[:600].  If the real tech requirements
    appear after character 600 (common when postings front-load company copy),
    Haiku scores against marketing text and may inflate or deflate the score.
    """

    @pytest.mark.api
    def test_false_positive_embedded_job_inflated_by_marketing_intro(self):
        """
        FALSE POSITIVE: An embedded-systems role front-loads Python/ML buzzwords in
        its company intro (within the first 600 chars).  The real requirements —
        C++, FPGA, VHDL — appear after the cutoff.

        Haiku sees "Python, ML, AI" in the intro and may over-score a candidate
        whose skills are entirely Python/web, producing a false positive.
        """
        full_requirements = _MARKETING_INTRO + _EMBEDDED_REQUIREMENTS
        truncated_requirements = full_requirements[:600]

        # Sanity-check: the embedded requirements are NOT in the truncated slice
        assert "C++" not in truncated_requirements
        assert "FPGA" not in truncated_requirements

        job_truncated = Job(
            company="TechCorp",
            role="Software Engineer Intern",
            location="Austin, TX",
            apply_link="https://techcorp.com/jobs/embed",
            requirements=truncated_requirements,   # simulates the 600-char cut
        )
        job_full = Job(
            company="TechCorp",
            role="Software Engineer Intern",
            location="Austin, TX",
            apply_link="https://techcorp.com/jobs/embed",
            requirements=full_requirements,        # full context available
        )

        score_truncated = haiku_score(job_truncated, SKILLS_STR, EXPERIENCES, False)
        score_full = haiku_score(job_full, SKILLS_STR, EXPERIENCES, False)

        print(
            f"\n[#2 false positive]\n"
            f"  truncated (600 chars, marketing copy only): fit={score_truncated['fit_score']}  "
            f"skills={score_truncated['skills_matched']}\n"
            f"  full requirements (embedded C++/FPGA visible): fit={score_full['fit_score']}  "
            f"skills={score_full['skills_matched']}"
        )

        # Diagnostic only — API run showed gap=0 for this job shape.
        # Issue #2 is not confirmed: Haiku scores the same whether or not C++/FPGA
        # requirements are visible, because the marketing intro already provides
        # enough Python/ML signal to anchor the score.
        gap = score_truncated["fit_score"] - score_full["fit_score"]
        print(f"  Score inflation from truncation: +{gap}")

    @pytest.mark.api
    def test_false_negative_good_requirements_after_cutoff(self):
        """
        FALSE NEGATIVE: A well-matched full-stack role buries its Python/React/SQL
        requirements after 600 chars of company boilerplate.

        Haiku only sees the boilerplate and may underestimate fit, potentially
        dropping a job the candidate is well-suited for.
        """
        # Good requirements hidden after 600-char boilerplate
        full_requirements = _MARKETING_INTRO + _FULLSTACK_REQUIREMENTS
        truncated_requirements = full_requirements[:600]

        assert "React" not in truncated_requirements
        assert "Python" not in truncated_requirements.split("About us:")[0]  # marketing mention only

        job_truncated = Job(
            company="Acme Corp",
            role="Software Engineer Intern",
            location="Remote",
            apply_link="https://acme.com/jobs/swe",
            requirements=truncated_requirements,
        )
        job_full = Job(
            company="Acme Corp",
            role="Software Engineer Intern",
            location="Remote",
            apply_link="https://acme.com/jobs/swe",
            requirements=full_requirements,
        )

        score_truncated = haiku_score(job_truncated, SKILLS_STR, EXPERIENCES, False)
        score_full = haiku_score(job_full, SKILLS_STR, EXPERIENCES, False)

        print(
            f"\n[#2 false negative]\n"
            f"  truncated (good reqs hidden after 600 chars): fit={score_truncated['fit_score']}\n"
            f"  full requirements visible:                     fit={score_full['fit_score']}\n"
            f"  Score suppression from truncation: -{score_full['fit_score'] - score_truncated['fit_score']}"
        )

        # Diagnostic only — API run showed gap=0 for this job shape.
        # Issue #2 is not confirmed: the marketing intro's Python mentions give
        # Haiku enough signal to score 8 regardless of what follows the cutoff.


# ===========================================================================
# ISSUE #6 — empty requirements (live API tests)
# ===========================================================================

class TestIssue6EmptyRequirements:
    """
    When requirements fetching fails, job.requirements == "".
    Haiku has no tech-stack signal and scores purely from the job title + company name.
    """

    @pytest.mark.api
    def test_false_positive_irrelevant_job_scores_high_with_empty_requirements(self):
        """
        FALSE POSITIVE: An embedded-systems role with no requirements page.
        Haiku sees only "Software Engineer Intern" as the title and may assign
        a high score because the title matches SWE patterns — despite the
        candidate having zero embedded experience.
        """
        job_no_reqs = Job(
            company="ChipMaker Inc",
            role="Software Engineer Intern",   # generic title hides the speciality
            location="San Jose, CA",
            apply_link="https://chipmaker.com/jobs/1",
            requirements="",
        )
        job_with_reqs = Job(
            company="ChipMaker Inc",
            role="Software Engineer Intern",
            location="San Jose, CA",
            apply_link="https://chipmaker.com/jobs/1",
            requirements=_EMBEDDED_REQUIREMENTS,
        )

        score_no_reqs = haiku_score(job_no_reqs, SKILLS_STR, EXPERIENCES, False)
        score_with_reqs = haiku_score(job_with_reqs, SKILLS_STR, EXPERIENCES, False)

        print(
            f"\n[#6 false positive]\n"
            f"  empty requirements:               fit={score_no_reqs['fit_score']}  "
            f"skills={score_no_reqs['skills_matched']}\n"
            f"  embedded requirements present:    fit={score_with_reqs['fit_score']}  "
            f"skills={score_with_reqs['skills_matched']}\n"
            f"  Score inflation from empty reqs: +{score_no_reqs['fit_score'] - score_with_reqs['fit_score']}"
        )

        assert score_no_reqs["fit_score"] > score_with_reqs["fit_score"], (
            "Empty requirements did not inflate the score for a mismatched job — "
            "#6 may not be producing false positives for this job shape."
        )
        # The false positive is confirmed when an irrelevant job clears the threshold
        assert score_no_reqs["fit_score"] >= 7, (
            f"No false positive: empty-requirements score ({score_no_reqs['fit_score']}) "
            "is below the gate threshold.  #6 is not a source of false positives here."
        )

    @pytest.mark.api
    def test_false_negative_good_job_underscore_with_empty_requirements(self):
        """
        FALSE NEGATIVE: A well-matched full-stack role with no requirements page.
        Haiku has no evidence that the role matches the candidate's stack and may
        under-score it, causing it to be dropped at the gate.
        """
        job_no_reqs = Job(
            company="GoodMatch Corp",
            role="Software Engineer Intern",
            location="Remote",
            apply_link="https://goodmatch.com/jobs/swe",
            requirements="",
        )
        job_with_reqs = Job(
            company="GoodMatch Corp",
            role="Software Engineer Intern",
            location="Remote",
            apply_link="https://goodmatch.com/jobs/swe",
            requirements=_FULLSTACK_REQUIREMENTS,
        )

        score_no_reqs = haiku_score(job_no_reqs, SKILLS_STR, EXPERIENCES, False)
        score_with_reqs = haiku_score(job_with_reqs, SKILLS_STR, EXPERIENCES, False)

        print(
            f"\n[#6 false negative]\n"
            f"  empty requirements:              fit={score_no_reqs['fit_score']}\n"
            f"  full matching requirements:      fit={score_with_reqs['fit_score']}\n"
            f"  Score suppression from missing reqs: -{score_with_reqs['fit_score'] - score_no_reqs['fit_score']}"
        )

        assert score_with_reqs["fit_score"] > score_no_reqs["fit_score"], (
            "Full requirements did not raise the score — empty requirements are not "
            "suppressing scores for this job shape.  #6 may not be a false-negative source."
        )

    @pytest.mark.api
    def test_score_variance_across_titles_with_empty_requirements(self):
        """
        With empty requirements, the only signal is the role title.
        This test shows how much scores vary across three title variants for the
        same underlying job, demonstrating how noisy scoring becomes without
        requirements content.
        """
        titles = [
            "Software Engineer Intern",
            "Backend Engineer Intern",
            "Engineering Intern",        # too generic — would be rejected at Stage 1
        ]
        scores = {}
        for title in titles:
            job = Job(
                company="NoisyCorp",
                role=title,
                location="Remote",
                apply_link=f"https://noisycorp.com/{title.replace(' ', '-')}",
                requirements="",
            )
            result = haiku_score(job, SKILLS_STR, EXPERIENCES, False)
            scores[title] = result["fit_score"]
            print(f"  '{title}': fit={result['fit_score']}")

        score_values = list(scores.values())
        spread = max(score_values) - min(score_values)
        print(f"\n[#6 title variance] spread across titles (empty reqs): {spread} points")
        print("  High spread = scoring is driven by title wording, not actual fit.")


# ===========================================================================
# COMBINED: #2 + #6 interaction
# ===========================================================================

class TestCombinedIssues:
    """
    The worst case: requirements fetch failed (#6) AND the job front-loads
    buzzwords before the real requirements (#2 would have applied if fetched).
    These two issues can interact to produce confidently wrong scores.
    """

    @pytest.mark.api
    def test_no_requirements_vs_truncated_vs_full(self):
        """
        Three-way comparison for the same embedded-systems job:
          A) No requirements (fetch failed)           — #6
          B) Truncated at 600 (marketing copy only)   — #2
          C) Full requirements (C++/FPGA visible)     — ground truth

        Expected ordering if both issues inflate scores: A ≥ B > C.
        """
        full_reqs = _MARKETING_INTRO + _EMBEDDED_REQUIREMENTS

        def make_job(reqs):
            return Job(
                company="SiliconCo",
                role="Software Engineer Intern",
                location="Austin, TX",
                apply_link="https://siliconco.com/jobs/swe",
                requirements=reqs,
            )

        score_none = haiku_score(make_job(""), SKILLS_STR, EXPERIENCES, False)
        score_trunc = haiku_score(make_job(full_reqs[:600]), SKILLS_STR, EXPERIENCES, False)
        score_full = haiku_score(make_job(full_reqs), SKILLS_STR, EXPERIENCES, False)

        print(
            f"\n[combined #2+#6]\n"
            f"  A) no requirements:     fit={score_none['fit_score']}\n"
            f"  B) truncated (600 ch):  fit={score_trunc['fit_score']}\n"
            f"  C) full requirements:   fit={score_full['fit_score']}\n"
        )

        # If C is the lowest, both issues are inflating scores.
        # If A==B==C, neither issue is contributing for this job shape.
        if score_full["fit_score"] < score_none["fit_score"] or score_full["fit_score"] < score_trunc["fit_score"]:
            print("  CONFIRMED: missing/truncated requirements inflate scores vs ground truth.")
        else:
            print("  NOT CONFIRMED: full requirements did not lower the score — "
                  "neither issue is a false-positive source for this job shape.")
