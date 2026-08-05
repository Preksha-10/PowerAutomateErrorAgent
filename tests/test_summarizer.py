"""
tests/test_summarizer.py

Tests for skills/summarizer.py.
Verifies correct extraction into Summary from a valid LLM response,
that a blank/missing executive_summary raises SummaryError, and that
developer_notes is treated as genuinely optional (empty string is
valid) unlike the other text fields in this project.
"""

import pytest

from skills.summarizer import Summary, SummaryError, extract_summary
from utils.llm_stub import get_stub_response


def make_llm_response(**overrides) -> dict:
    """
    Helper: a realistic shared LLM response generated via the actual
    stub, so this test exercises the real llm_stub <-> summarizer
    contract rather than a hand-built dict that could drift from
    reality.
    """
    payload = dict(
        flow_name="Invoice Approval Flow",
        environment="Production",
        action_name="Get Excel Rows",
        action_type="Excel",
        exception="FileLockedException",
        error_message="The file is locked by another process.",
        timestamp="2026-01-15T09:30:00",
        machine_name="GATEWAY-VM-01",
        has_screenshot=False,
    )
    response = get_stub_response(payload)
    response.update(overrides)
    return response


def test_extract_summary_returns_populated_dataclass():
    """A valid LLM response should produce a Summary with both fields
    populated from the response."""
    response = make_llm_response()

    result = extract_summary(response)

    assert isinstance(result, Summary)
    assert result.executive_summary == response["executive_summary"]
    assert result.developer_notes == response["developer_notes"]


def test_blank_executive_summary_is_rejected():
    """
    executive_summary is the one line a non-technical reader sees
    first — a blank string is a broken response, not a valid edge
    case, and must raise SummaryError.
    """
    response = make_llm_response(executive_summary="   ")

    with pytest.raises(SummaryError, match="executive_summary"):
        extract_summary(response)


def test_missing_executive_summary_is_rejected():
    """A response missing the key entirely (not just blank) should
    also fail clearly rather than raising a bare KeyError downstream."""
    response = make_llm_response()
    del response["executive_summary"]

    with pytest.raises(SummaryError, match="executive_summary"):
        extract_summary(response)


def test_empty_developer_notes_is_accepted():
    """
    Unlike executive_summary, an empty developer_notes is genuinely
    valid — it matches IncidentReport's own default of "" and reflects
    an LLM simply having nothing extra to flag. This must NOT raise.
    """
    response = make_llm_response(developer_notes="")

    result = extract_summary(response)

    assert result.developer_notes == ""


def test_missing_developer_notes_defaults_to_empty_string():
    """If the LLM response omits developer_notes entirely, extraction
    should default it to "" rather than raising or storing None."""
    response = make_llm_response()
    del response["developer_notes"]

    result = extract_summary(response)

    assert result.developer_notes == ""


def test_non_string_developer_notes_is_rejected():
    """developer_notes must still be a string type when present — a
    non-string value (e.g. the LLM returned a list) should fail
    clearly rather than propagate into IncidentReport construction."""
    response = make_llm_response(developer_notes=["not", "a", "string"])

    with pytest.raises(SummaryError, match="developer_notes"):
        extract_summary(response)