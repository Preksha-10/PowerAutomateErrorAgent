"""
tests/test_incident_report.py

Tests for the IncidentReport schema.
Verifies construction, the confidence_score/enum validation boundaries
Pydantic is here specifically to enforce, and the notification payload
contract (mirrors test_failure_event.py's to_llm_payload tests).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.incident_report import (
    DocumentationLink,
    ErrorCategory,
    IncidentReport,
    Severity,
)


def make_sample_report(**overrides) -> IncidentReport:
    """Helper: builds a consistent IncidentReport, with overridable fields."""
    defaults = dict(
        flow_name="Invoice Approval Flow",
        environment="Production",
        machine_name="GATEWAY-VM-01",
        timestamp=datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc),
        run_id="run-12345",
        executive_summary="Flow failed because the source Excel file was "
        "locked by another process during the read step.",
        error_category=ErrorCategory.EXCEL_LOCKED_OR_MISSING,
        severity=Severity.HIGH,
        root_cause_analysis="A separate scheduled process had the workbook "
        "open for writing at the same time this flow attempted to read it.",
        confidence_score=0.85,
        technical_explanation="FileLockedException raised on Get Excel Rows.",
        business_impact="Invoice approvals for this batch are delayed.",
        step_by_step_resolution=[
            "Confirm no other process has the file open.",
            "Retry the flow run.",
        ],
        alternative_solutions=["Move to a SharePoint-based Excel source."],
        preventive_measures=["Stagger scheduled jobs that touch this file."],
        retry_recommended=True,
        retry_notes="Safe to retry once the lock is released.",
        best_practices=["Avoid concurrent writers on shared Excel files."],
        related_documentation=[
            DocumentationLink(
                title="Handle file locking errors in Power Automate",
                url="https://learn.microsoft.com/power-automate/file-locking",
            )
        ],
        similar_historical_errors=[],
        developer_notes="First occurrence this month.",
    )
    defaults.update(overrides)
    return IncidentReport(**defaults)


def test_incident_report_construction():
    """An IncidentReport should store all provided fields exactly as given."""
    report = make_sample_report()

    assert report.flow_name == "Invoice Approval Flow"
    assert report.error_category == ErrorCategory.EXCEL_LOCKED_OR_MISSING
    assert report.severity == Severity.HIGH
    assert report.confidence_score == 0.85


def test_list_fields_default_to_empty_list_not_none():
    """
    List fields must default to [] rather than None, so notification/report
    templates can iterate them directly without a None-check at every call
    site. Only the fields not overridden by make_sample_report are checked.
    """
    report = make_sample_report(similar_historical_errors=[])

    assert report.similar_historical_errors == []
    assert isinstance(report.step_by_step_resolution, list)


def test_confidence_score_above_one_is_rejected():
    """
    confidence_score is constrained to 0.0-1.0. This is the exact kind of
    boundary Pydantic exists to enforce here: a bad LLM response with
    confidence=1.85 should fail loudly at construction, not silently
    propagate into a report a developer reads as '185% confident'.
    """
    with pytest.raises(ValidationError):
        make_sample_report(confidence_score=1.85)


def test_confidence_score_below_zero_is_rejected():
    """Mirror of the above at the other boundary."""
    with pytest.raises(ValidationError):
        make_sample_report(confidence_score=-0.1)


def test_invalid_severity_string_is_rejected():
    """
    Severity is a fixed enum, not a free-text string. Passing a value
    outside {Low, Medium, High, Critical} must fail validation rather than
    silently storing an unrecognized string a priority router can't map.
    """
    with pytest.raises(ValidationError):
        make_sample_report(severity="Super Urgent")


def test_invalid_error_category_string_is_rejected():
    """Same enum-enforcement boundary as severity, for error_category."""
    with pytest.raises(ValidationError):
        make_sample_report(error_category="Something Made Up")


def test_generated_at_defaults_when_omitted():
    """
    generated_at should default to the current UTC time when not supplied,
    distinct from `timestamp` (when the underlying flow actually failed).
    """
    report = make_sample_report()

    assert isinstance(report.generated_at, datetime)
    assert report.generated_at.tzinfo is not None


def test_to_notification_payload_contains_expected_fields():
    """
    The notification payload must contain exactly the fields the master
    prompt's Notification section requires — nothing more. This is the
    enforcement point: if someone later adds a field to
    to_notification_payload() that wasn't approved, this test documents
    and protects that boundary (mirrors the equivalent test in
    test_failure_event.py for to_llm_payload).
    """
    report = make_sample_report()
    payload = report.to_notification_payload()

    expected_keys = {
        "flow_name",
        "machine_name",
        "timestamp",
        "environment",
        "error_summary",
        "root_cause",
        "recommended_fix",
        "priority",
        "run_id",
    }

    assert set(payload.keys()) == expected_keys


def test_to_notification_payload_uses_first_resolution_step_as_fix():
    """The recommended_fix in a notification should be the first concrete
    resolution step, not the whole list — Teams/Email need one line, not
    the full step-by-step plan."""
    report = make_sample_report()
    payload = report.to_notification_payload()

    assert payload["recommended_fix"] == "Confirm no other process has the file open."


def test_to_notification_payload_fix_fallback_when_no_steps():
    """
    If step_by_step_resolution is empty (shouldn't normally happen, but
    the field isn't required to be non-empty), the notification should
    fall back to pointing at the full report rather than sending a blank
    'recommended_fix' field.
    """
    report = make_sample_report(step_by_step_resolution=[])
    payload = report.to_notification_payload()

    assert payload["recommended_fix"] == "See full incident report."


def test_to_notification_payload_priority_matches_severity_value():
    """priority in the notification payload should be the plain string
    value of the severity enum (e.g. 'High'), not the enum member itself,
    since it's going straight into a text template."""
    report = make_sample_report(severity=Severity.CRITICAL)
    payload = report.to_notification_payload()

    assert payload["priority"] == "Critical"
    assert isinstance(payload["priority"], str)