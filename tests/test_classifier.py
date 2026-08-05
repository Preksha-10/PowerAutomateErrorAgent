"""
tests/test_classifier.py

Tests for skills/classifier.py.
Verifies correct extraction/typing from a valid LLM response, and that
both malformed category and malformed severity values raise
ClassificationError with a message identifying which field was bad.
"""

import pytest

from models.incident_report import ErrorCategory, Severity
from skills.classifier import ClassificationError, classify
from utils.llm_stub import get_stub_response


def make_llm_response(**overrides) -> dict:
    """
    Helper: a realistic shared LLM response, generated via the actual
    stub so this test exercises the real contract between llm_stub and
    classifier, not a hand-built dict that could drift from reality.
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


def test_classify_returns_typed_enum_tuple():
    """A valid LLM response should return (ErrorCategory, Severity) enum
    members, not raw strings."""
    response = make_llm_response()

    category, severity = classify(response)

    assert isinstance(category, ErrorCategory)
    assert isinstance(severity, Severity)
    assert category == ErrorCategory.EXCEL_LOCKED_OR_MISSING
    assert severity == Severity.HIGH


def test_classify_rejects_unrecognized_error_category():
    """
    A category value outside the fixed vocabulary must raise
    ClassificationError with a message identifying error_category
    specifically, not a generic/opaque failure.
    """
    response = make_llm_response(error_category="Something Made Up")

    with pytest.raises(ClassificationError, match="error_category"):
        classify(response)


def test_classify_rejects_unrecognized_severity():
    """Mirror of the above for severity."""
    response = make_llm_response(severity="Super Urgent")

    with pytest.raises(ClassificationError, match="severity"):
        classify(response)


def test_classify_rejects_missing_error_category():
    """A response missing the error_category key entirely (not just an
    invalid value) should still fail clearly rather than raising a bare
    KeyError somewhere downstream."""
    response = make_llm_response()
    del response["error_category"]

    with pytest.raises(ClassificationError):
        classify(response)


def test_classify_error_message_lists_valid_options():
    """
    The exception message should list the valid vocabulary, so a
    developer reading a failed test or a production log immediately
    sees what values ARE acceptable, not just that the given one wasn't.
    """
    response = make_llm_response(severity="Nope")

    with pytest.raises(ClassificationError) as exc_info:
        classify(response)

    assert "Low" in str(exc_info.value)
    assert "Critical" in str(exc_info.value)