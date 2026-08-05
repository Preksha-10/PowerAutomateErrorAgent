"""
tests/test_notification_tool.py

Tests for tools/notification_tool.py.
Verifies the shared template renders all required fields, that Teams
and Email dispatch both use that same template, that multi-channel
send returns one result per channel, and that the stubbed transport
actually logs (proving something was "sent") using pytest's caplog
fixture.
"""

import logging
from datetime import datetime, timezone

from models.incident_report import (
    DocumentationLink,
    ErrorCategory,
    IncidentReport,
    Severity,
)
from tools.notification_tool import (
    NotificationChannel,
    NotificationResult,
    send_email_notification,
    send_notification,
    send_teams_notification,
)


def make_sample_report(**overrides) -> IncidentReport:
    """Helper: builds a consistent IncidentReport for notification tests."""
    defaults = dict(
        flow_name="Invoice Approval Flow",
        environment="Production",
        machine_name="GATEWAY-VM-01",
        timestamp=datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc),
        run_id="run-12345",
        executive_summary="Flow failed because the source Excel file was locked.",
        error_category=ErrorCategory.EXCEL_LOCKED_OR_MISSING,
        severity=Severity.HIGH,
        root_cause_analysis="A separate scheduled process had the workbook open.",
        confidence_score=0.85,
        technical_explanation="FileLockedException raised on Get Excel Rows.",
        business_impact="Invoice approvals for this batch are delayed.",
        step_by_step_resolution=[
            "Confirm no other process has the file open.",
            "Retry the flow run.",
        ],
        retry_recommended=True,
    )
    defaults.update(overrides)
    return IncidentReport(**defaults)


def test_send_teams_notification_returns_successful_result():
    """Sending via Teams should return a NotificationResult marked
    successful, tagged with the TEAMS channel."""
    report = make_sample_report()

    result = send_teams_notification(report)

    assert isinstance(result, NotificationResult)
    assert result.channel == NotificationChannel.TEAMS
    assert result.success is True


def test_send_email_notification_returns_successful_result():
    """Mirror of the Teams test, for Email."""
    report = make_sample_report()

    result = send_email_notification(report)

    assert result.channel == NotificationChannel.EMAIL
    assert result.success is True


def test_rendered_message_contains_all_required_fields():
    """
    The rendered message must include every field the master prompt's
    Notification section requires: Flow Name, Machine Name, Timestamp,
    Environment, Error Summary, Root Cause, Recommended Fix, Priority,
    and a run reference.
    """
    report = make_sample_report()

    result = send_teams_notification(report)

    assert "Invoice Approval Flow" in result.rendered_message
    assert "GATEWAY-VM-01" in result.rendered_message
    assert "Production" in result.rendered_message
    assert "High" in result.rendered_message
    assert "Excel file was locked" in result.rendered_message
    assert "workbook open" in result.rendered_message
    assert "Confirm no other process has the file open." in result.rendered_message
    assert "run-12345" in result.rendered_message


def test_teams_and_email_use_the_same_template():
    """
    Per the master prompt: template once, reuse for both channels. The
    rendered message body should be identical regardless of which
    channel it's sent through.
    """
    report = make_sample_report()

    teams_result = send_teams_notification(report)
    email_result = send_email_notification(report)

    assert teams_result.rendered_message == email_result.rendered_message


def test_missing_run_id_renders_a_placeholder_not_a_crash():
    """
    run_id is Optional on IncidentReport. The template must handle a
    None run_id gracefully with a placeholder line, not raise or render
    the literal string 'None'.
    """
    report = make_sample_report(run_id=None)

    result = send_teams_notification(report)

    assert "not available" in result.rendered_message
    assert "None" not in result.rendered_message.split("Run ID:")[1].split("\n")[0]


def test_send_notification_dispatches_to_multiple_channels():
    """
    send_notification() with both channels requested should return two
    results, one per channel, in the order requested.
    """
    report = make_sample_report()

    results = send_notification(
        report, [NotificationChannel.TEAMS, NotificationChannel.EMAIL]
    )

    assert len(results) == 2
    assert results[0].channel == NotificationChannel.TEAMS
    assert results[1].channel == NotificationChannel.EMAIL


def test_stub_transport_actually_logs_the_message(caplog):
    """
    Proves the stub transport does something observable (logs) rather
    than being a no-op that would let a broken call site pass tests
    silently. Uses caplog since there's no real API call to assert
    against yet.
    """
    report = make_sample_report()

    with caplog.at_level(logging.INFO):
        send_teams_notification(report)

    assert any("TEAMS NOTIFICATION" in record.message for record in caplog.records)