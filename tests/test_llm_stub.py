"""
tests/test_llm_stub.py

Tests for the mocked LLM call in utils/llm_stub.py.
Verifies that different failure inputs produce different canned
responses (proving the stub isn't just one fixed blob regardless of
input), that the response shape matches what prompts/summary_fix.md
requires, and that the JSON-string variant round-trips correctly.
"""

import json

from utils.llm_stub import get_stub_response, get_stub_response_as_json_string

EXPECTED_KEYS = {
    "error_category",
    "severity",
    "root_cause_analysis",
    "confidence_score",
    "technical_explanation",
    "business_impact",
    "executive_summary",
    "step_by_step_resolution",
    "alternative_solutions",
    "preventive_measures",
    "retry_recommended",
    "retry_notes",
    "best_practices",
    "developer_notes",
}


def make_payload(**overrides) -> dict:
    """Helper: a baseline payload shaped like FailureEvent.to_llm_payload()."""
    defaults = dict(
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
    defaults.update(overrides)
    return defaults


def test_response_contains_all_expected_keys():
    """
    Every key prompts/summary_fix.md's Output Format section requires
    must be present, since skills/*.py will build an IncidentReport
    directly from this dict's keys.
    """
    payload = make_payload()
    response = get_stub_response(payload)

    assert set(response.keys()) == EXPECTED_KEYS


def test_excel_locked_pattern_is_matched():
    """An Excel-lock error message should route to the excel_locked
    canned response, not the generic fallback."""
    payload = make_payload(
        exception="FileLockedException",
        error_message="The file is locked by another process.",
    )
    response = get_stub_response(payload)

    assert response["error_category"] == "Excel Locked/Missing"


def test_timeout_pattern_is_matched():
    """A timeout exception should route to the timeout canned response."""
    payload = make_payload(
        exception="SeleniumTimeoutException",
        error_message="Timed out waiting for element.",
        action_type="Browser Automation",
    )
    response = get_stub_response(payload)

    assert response["error_category"] == "Browser Timeout"


def test_auth_failed_pattern_is_matched():
    """A 401/unauthorized error should route to the auth_failed response,
    and critically, retry_recommended must be False — retrying without
    fixing credentials would fail identically."""
    payload = make_payload(
        exception="UnauthorizedException",
        error_message="401 Unauthorized: token expired.",
    )
    response = get_stub_response(payload)

    assert response["error_category"] == "Authentication Failed"
    assert response["retry_recommended"] is False


def test_unknown_pattern_falls_back_to_unexpected():
    """
    An error matching none of the known patterns must fall back to the
    Unexpected Exception category rather than raising or defaulting to
    an arbitrary one — mirrors ErrorCategory.UNEXPECTED_EXCEPTION being
    the deliberate fallback in the real schema.
    """
    payload = make_payload(
        exception="SomeBrandNewErrorType",
        error_message="Something nobody has seen before.",
        action_type="Custom Connector",
    )
    response = get_stub_response(payload)

    assert response["error_category"] == "Unexpected Exception"
    assert response["confidence_score"] < 0.5


def test_different_inputs_produce_different_responses():
    """
    Proves the stub isn't a single fixed blob returned regardless of
    input. If a future refactor accidentally collapses all patterns to
    one canned response, this test catches it.
    """
    excel_response = get_stub_response(
        make_payload(exception="FileLockedException", error_message="locked")
    )
    auth_response = get_stub_response(
        make_payload(exception="UnauthorizedException", error_message="401")
    )

    assert excel_response["error_category"] != auth_response["error_category"]


def test_response_is_a_fresh_copy_not_a_shared_reference():
    """
    Mutating one response must not corrupt the canned template used by
    the next call — get_stub_response() must return a copy, not the
    same dict object every time.
    """
    payload = make_payload()
    first = get_stub_response(payload)
    first["executive_summary"] = "MUTATED"

    second = get_stub_response(payload)

    assert second["executive_summary"] != "MUTATED"


def test_json_string_variant_round_trips_to_same_content():
    """
    The real LLM will return text that needs json.loads(), not a
    pre-parsed dict. This test exercises that exact parsing step, so a
    skill that only ever gets tested against get_stub_response() (the
    dict version) doesn't silently skip the parsing logic it will need
    against a real model response.
    """
    payload = make_payload()
    json_string = get_stub_response_as_json_string(payload)

    assert isinstance(json_string, str)
    parsed = json.loads(json_string)
    assert set(parsed.keys()) == EXPECTED_KEYS


def test_confidence_score_is_within_valid_range_for_every_pattern():
    """
    Every canned response's confidence_score must already satisfy the
    0.0-1.0 bound IncidentReport enforces at the schema level — if a
    canned response ever drifts outside that range, the skill building
    an IncidentReport from it would fail validation downstream, and
    this test catches that here instead of in a confusing place later.
    """
    test_cases = [
        make_payload(exception="FileLockedException", error_message="locked"),
        make_payload(exception="TimeoutException", error_message="timeout"),
        make_payload(exception="UnauthorizedException", error_message="401"),
        make_payload(error_message="element not found: selector stale"),
        make_payload(exception="Unknown", error_message="never seen this"),
    ]

    for payload in test_cases:
        response = get_stub_response(payload)
        assert 0.0 <= response["confidence_score"] <= 1.0