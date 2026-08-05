"""
tests/test_fix_recommendation.py

Tests for skills/fix_recommendation.py.
Verifies correct extraction into FixRecommendation from a valid LLM
response, that step_by_step_resolution must be non-empty while other
list fields may be empty, that blank items inside any list are
rejected, and that retry_recommended must be a real bool.
"""

import pytest

from skills.fix_recommendation import (
    FixRecommendation,
    FixRecommendationError,
    extract_fix_recommendation,
)
from utils.llm_stub import get_stub_response


def make_llm_response(**overrides) -> dict:
    """
    Helper: a realistic shared LLM response generated via the actual
    stub, so this test exercises the real llm_stub <-> fix_recommendation
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


def test_extract_fix_recommendation_returns_populated_dataclass():
    """A valid LLM response should produce a FixRecommendation with all
    fields populated from the response."""
    response = make_llm_response()

    result = extract_fix_recommendation(response)

    assert isinstance(result, FixRecommendation)
    assert result.step_by_step_resolution == response["step_by_step_resolution"]
    assert result.retry_recommended == response["retry_recommended"]
    assert result.alternative_solutions == response["alternative_solutions"]


def test_empty_step_by_step_resolution_is_rejected():
    """
    step_by_step_resolution must contain at least one step — a report
    with zero resolution steps gives a developer nothing to act on,
    unlike the other list fields which may legitimately be empty.
    """
    response = make_llm_response(step_by_step_resolution=[])

    with pytest.raises(FixRecommendationError, match="step_by_step_resolution"):
        extract_fix_recommendation(response)


def test_empty_alternative_solutions_is_accepted():
    """Unlike step_by_step_resolution, an empty alternative_solutions
    list is genuinely valid — not every failure has a viable
    alternative approach."""
    response = make_llm_response(alternative_solutions=[])

    result = extract_fix_recommendation(response)

    assert result.alternative_solutions == []


def test_empty_preventive_measures_is_accepted():
    """Same optionality as alternative_solutions, for preventive_measures."""
    response = make_llm_response(preventive_measures=[])

    result = extract_fix_recommendation(response)

    assert result.preventive_measures == []


def test_blank_item_in_step_by_step_resolution_is_rejected():
    """A list that's technically non-empty but contains a blank string
    is still a broken response — one useless step among real ones."""
    response = make_llm_response(
        step_by_step_resolution=["Check the file lock.", "   "]
    )

    with pytest.raises(FixRecommendationError, match="step_by_step_resolution"):
        extract_fix_recommendation(response)


def test_non_list_alternative_solutions_is_rejected():
    """A field that should be a list but is a string instead (e.g. the
    LLM returned prose instead of a list) must fail clearly."""
    response = make_llm_response(alternative_solutions="just retry it")

    with pytest.raises(FixRecommendationError, match="alternative_solutions"):
        extract_fix_recommendation(response)


def test_retry_recommended_must_be_real_bool_not_string():
    """
    A future automated-retry system may act on retry_recommended
    directly, so a loosely-typed value like the string "true" must be
    rejected rather than silently treated as truthy.
    """
    response = make_llm_response(retry_recommended="true")

    with pytest.raises(FixRecommendationError, match="retry_recommended"):
        extract_fix_recommendation(response)


def test_retry_recommended_missing_is_rejected():
    """A response missing retry_recommended entirely should fail
    clearly rather than defaulting silently to some assumed value."""
    response = make_llm_response()
    del response["retry_recommended"]

    with pytest.raises(FixRecommendationError, match="retry_recommended"):
        extract_fix_recommendation(response)


def test_retry_notes_none_is_accepted():
    """retry_notes is allowed to be null/None — not every recommendation
    needs a qualifying note."""
    response = make_llm_response(retry_notes=None)

    result = extract_fix_recommendation(response)

    assert result.retry_notes is None


def test_retry_notes_non_string_non_none_is_rejected():
    """retry_notes must be a string or None — anything else (e.g. a
    number) should fail clearly."""
    response = make_llm_response(retry_notes=12345)

    with pytest.raises(FixRecommendationError, match="retry_notes"):
        extract_fix_recommendation(response)