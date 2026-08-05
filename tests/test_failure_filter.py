"""Tests for skills/failure_filter.py — pure function, no I/O, no
mocking needed. Hand-built FlowRecord/ExceptionRecord lists."""

from datetime import datetime

from models.flow_record import FlowRecord, FlowStatus, FlowType
from models.exception_record import ExceptionRecord, ExceptionStatus
from skills.failure_filter import filter_and_join


def _flow(flow_id="f-1", status=FlowStatus.ENABLED):
    return FlowRecord(
        flow_id=flow_id,
        flow_name="Invoice Sync",
        environment="Production",
        owner="finance-team@example.com",
        status=status,
        flow_type=FlowType.CLOUD,
    )


def _exception(exception_id, run_id, timestamp, related_flow_id="f-1", status=ExceptionStatus.FAILED):
    return ExceptionRecord(
        exception_id=exception_id,
        related_flow_id=related_flow_id,
        run_id=run_id,
        error_message="UI element not found",
        exception_type="ElementNotFound",
        action_name="Click Submit",
        timestamp=timestamp,
        status=status,
    )


def test_discards_exceptions_from_disabled_flows():
    """An exception tied to a disabled flow must never surface as a
    FailureEvent — this is the core noise-reduction rule the whole
    detection pipeline depends on."""
    flows = [_flow(status=FlowStatus.DISABLED)]
    exceptions = [_exception("e-1", "r-1", datetime(2025, 1, 1, 10, 0))]
    result = filter_and_join(flows, exceptions)
    assert result == []


def test_discards_exceptions_for_unknown_flow_id():
    """An orphaned exception (flow deleted/not in our monitored set)
    must be dropped, not crash the join."""
    flows = [_flow(flow_id="f-1")]
    exceptions = [_exception("e-1", "r-1", datetime(2025, 1, 1, 10, 0), related_flow_id="f-999")]
    result = filter_and_join(flows, exceptions)
    assert result == []


def test_discards_resolved_exceptions():
    """Resolved exceptions must never produce a FailureEvent — only
    active failures matter to the AI reasoning step."""
    flows = [_flow()]
    exceptions = [_exception("e-1", "r-1", datetime(2025, 1, 1, 10, 0), status=ExceptionStatus.RESOLVED)]
    result = filter_and_join(flows, exceptions)
    assert result == []


def test_dedupes_retry_chain_keeps_latest_and_counts_retries():
    """Three exception rows from the same run_id (retry chain) must
    collapse into exactly one FailureEvent — this is the mechanism
    that prevents flooding developers with 3 alerts for 1 real
    incident."""
    flows = [_flow()]
    exceptions = [
        _exception("e-1", "r-1", datetime(2025, 1, 1, 10, 0, 0)),
        _exception("e-2", "r-1", datetime(2025, 1, 1, 10, 5, 0)),
        _exception("e-3", "r-1", datetime(2025, 1, 1, 10, 10, 0)),  # latest
    ]
    result = filter_and_join(flows, exceptions)
    assert len(result) == 1
    assert result[0].timestamp == datetime(2025, 1, 1, 10, 10, 0)


def test_produces_one_event_per_distinct_run():
    """Two separate runs of the same flow, each failing once, must
    produce two distinct FailureEvents — dedup must key on run_id,
    not flow_id."""
    flows = [_flow()]
    exceptions = [
        _exception("e-1", "r-1", datetime(2025, 1, 1, 10, 0)),
        _exception("e-2", "r-2", datetime(2025, 1, 1, 11, 0)),
    ]
    result = filter_and_join(flows, exceptions)
    assert len(result) == 2

def test_cloud_flow_exception_with_no_machine_name_defaults_to_na():
    """Cloud Flow exceptions have no machine_name (PAD-only field) —
    must fall back to 'N/A' rather than crash on FailureEvent's
    required str field."""
    flows = [_flow()]
    exceptions = [_exception("e-1", "r-1", datetime(2025, 1, 1, 10, 0))]
    result = filter_and_join(flows, exceptions)
    assert result[0].machine_name == "N/A"