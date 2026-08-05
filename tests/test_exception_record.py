"""Tests for models/exception_record.py — no network calls. Uses
in-memory dicts shaped like mock Dataverse rows."""

import pytest
from datetime import datetime

from models.exception_record import ExceptionRecord, ExceptionStatus


def test_is_active_failure_true_for_failed_status():
    """A Failed exception must be flagged active — this is the gate
    that decides whether an exception even enters the join with
    FlowRecord in failure_filter.py."""
    exc = ExceptionRecord(
        exception_id="e-1",
        related_flow_id="f-1",
        run_id="r-1",
        error_message="UI element not found",
        exception_type="ElementNotFound",
        action_name="Click Submit Button",
        timestamp=datetime(2025, 1, 1, 10, 0, 0),
        status=ExceptionStatus.FAILED,
        machine_name="DESKTOP-01",
    )
    assert exc.is_active_failure is True


def test_is_active_failure_false_for_resolved_status():
    """A Resolved exception must NOT be treated as active — already-
    handled incidents shouldn't re-trigger the AI pipeline and waste
    an LLM call."""
    exc = ExceptionRecord(
        exception_id="e-2",
        related_flow_id="f-1",
        run_id="r-2",
        error_message="Timeout",
        exception_type="Timeout",
        action_name="Wait For Response",
        timestamp=datetime(2025, 1, 1, 11, 0, 0),
        status=ExceptionStatus.RESOLVED,
    )
    assert exc.is_active_failure is False


def test_from_dataverse_dict_parses_timestamp_and_optional_fields():
    """Confirms the ISO string -> datetime conversion happens exactly
    once here, and that optional Cloud-Flow-only records (no
    machine_name/severity) don't blow up on missing keys."""
    raw = {
        "exception_id": "e-3",
        "related_flow_id": "f-2",
        "run_id": "r-3",
        "error_message": "HTTP 401 Unauthorized",
        "exception_type": "AuthenticationFailed",
        "action_name": "Call REST API",
        "timestamp": "2025-01-02T09:30:00",
        "status": "Failed",
    }
    exc = ExceptionRecord.from_dataverse_dict(raw)
    assert exc.timestamp == datetime(2025, 1, 2, 9, 30, 0)
    assert exc.machine_name is None
    assert exc.severity is None
    assert exc.is_active_failure is True


def test_from_dataverse_dict_rejects_unknown_status():
    """Same defensive rationale as FlowRecord — an unrecognized status
    value should fail loudly at the boundary, not silently corrupt
    is_active_failure downstream."""
    raw = {
        "exception_id": "e-4",
        "related_flow_id": "f-2",
        "run_id": "r-4",
        "error_message": "Unknown",
        "exception_type": "Unknown",
        "action_name": "N/A",
        "timestamp": "2025-01-02T09:30:00",
        "status": "Escalated",  # not a real ExceptionStatus value
    }
    with pytest.raises(ValueError):
        ExceptionRecord.from_dataverse_dict(raw)