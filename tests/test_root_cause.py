"""
tests/test_root_cause.py

Tests for skills/root_cause.py.
Verifies correct extraction into RootCauseAnalysis from a valid LLM
response, and that blank text fields, missing fields, and out-of-range
or wrong-typed confidence_score values all raise RootCauseError.
"""

import pytest

from skills.root_cause import RootCauseAnalysis, RootCauseError, extract_root_cause
from utils.llm_stub import get_stub_response


def make_llm_response(**overrides) -> dict:
    """
    Helper: a realistic shared LLM response generated via the actual
    stub, so this test exercises the real llm_stub <-> root_cause
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


def test_extract_root_cause_returns_populated_dataclass():
    """A valid LLM response should produce a RootCauseAnalysis with all
    four fields populated from the response."""
    response = make_llm_response()

    result = extract_root_cause(response)

    assert isinstance(result, RootCauseAnalysis)
    assert result.root_cause_analysis == response["root_cause_analysis"]
    assert result.confidence_score == response["confidence_score"]
    assert result.technical_explanation == response["technical_explanation"]
    assert result.business_impact == response["business_impact"]


def test_confidence_score_above_one_is_rejected():
    """Mirrors the bound IncidentReport enforces at the schema level —
    catching it here means a bad LLM response fails at the reasoning
    stage, not three steps later during report assembly."""
    response = make_llm_response(confidence_score=1.5)

    with pytest.raises(RootCauseError, match="confidence_score"):
        extract_root_cause(response)


def test_confidence_score_below_zero_is_rejected():
    """Mirror of the above at the other boundary."""
    response = make_llm_response(confidence_score=-0.2)

    with pytest.raises(RootCauseError, match="confidence_score"):
        extract_root_cause(response)


def test_confidence_score_wrong_type_is_rejected():
    """A confidence_score that isn't a number at all (e.g. the LLM
    returned the string 'high') must fail clearly rather than crash
    later with a confusing type error during comparison."""
    response = make_llm_response(confidence_score="high")

    with pytest.raises(RootCauseError, match="confidence_score"):
        extract_root_cause(response)


def test_blank_root_cause_analysis_is_rejected():
    """
    An LLM response that technically has the root_cause_analysis key
    but returns an empty string is still broken — silently accepting it
    would produce an IncidentReport with a blank root cause.
    """
    response = make_llm_response(root_cause_analysis="   ")

    with pytest.raises(RootCauseError, match="root_cause_analysis"):
        extract_root_cause(response)


def test_missing_technical_explanation_is_rejected():
    """A response missing the key entirely (not just blank) should also
    fail clearly rather than raising a bare KeyError downstream."""
    response = make_llm_response()
    del response["technical_explanation"]

    with pytest.raises(RootCauseError, match="technical_explanation"):
        extract_root_cause(response)


def test_blank_business_impact_is_rejected():
    """Same blank-field guard as root_cause_analysis, applied to
    business_impact."""
    response = make_llm_response(business_impact="")

    with pytest.raises(RootCauseError, match="business_impact"):
        extract_root_cause(response)