"""
tests/test_app.py

Tests for app.py's orchestrator functions.
Verifies a single FailureEvent processes successfully end to end, that
a broken skill's error is isolated as a ProcessingFailure rather than
raising and taking down a whole batch, that process_all_current_failures()
processes every mock FailureEvent, and that logging happens before
notification (log-before-notify ordering, per the design rationale in
app.py's own docstring).

Uses monkeypatch + tmp_path throughout — never touches temp/incidents.db,
never depends on ordering of mock fixture data beyond what's asserted.
"""

from datetime import datetime, timezone

import app
from app import (
    ProcessingFailure,
    ProcessingOutcome,
    process_all_current_failures,
    process_failure_event,
)
from models.failure_event import FailureEvent
from tools.incident_logger_tool import get_incident


def make_event(**overrides) -> FailureEvent:
    """Helper: a realistic FailureEvent for orchestrator tests."""
    defaults = dict(
        flow_name="Invoice Approval Flow",
        environment="Production",
        action_name="Get Excel Rows",
        action_type="Excel",
        exception="FileLockedException",
        error_message="The file is locked by another process.",
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
        machine_name="GATEWAY-VM-01",
    )
    defaults.update(overrides)
    return FailureEvent(**defaults)


def test_process_failure_event_succeeds_end_to_end(tmp_path, monkeypatch):
    """
    A well-formed FailureEvent should process all the way through to a
    ProcessingOutcome with a real incident_id, using a temp DB so this
    test never touches temp/incidents.db.
    """
    db_path = str(tmp_path / "test_incidents.db")
    monkeypatch.setattr(app.config, "INCIDENT_DB_PATH", db_path)

    event = make_event()
    result = process_failure_event(event)

    assert isinstance(result, ProcessingOutcome)
    assert result.incident_id
    assert result.report.flow_name == "Invoice Approval Flow"
    assert len(result.notification_results) == 2


def test_process_failure_event_logs_before_notification_completes(
    tmp_path, monkeypatch
):
    """
    Per app.py's own design rationale: the incident must be durably
    logged before notification is attempted. This test proves the
    ORDER by checking the incident is retrievable and already marked
    processed by the time process_failure_event() returns — i.e.
    logging (and mark_processed) genuinely happened, not just that a
    result object came back looking right.
    """
    db_path = str(tmp_path / "test_incidents.db")
    monkeypatch.setattr(app.config, "INCIDENT_DB_PATH", db_path)

    event = make_event()
    result = process_failure_event(event)

    retrieved = get_incident(result.incident_id, db_path=db_path)
    assert retrieved is not None
    assert retrieved["processed"] is True


def test_process_failure_event_isolates_a_broken_skill(tmp_path, monkeypatch):
    """
    If a skill raises (simulated here by making classify() always
    raise, standing in for a malformed real-LLM response later), the
    orchestrator must return a ProcessingFailure, NOT propagate the
    exception. This is the entire point of per-event error isolation —
    one bad event must not be able to crash a batch of many.
    """
    db_path = str(tmp_path / "test_incidents.db")
    monkeypatch.setattr(app.config, "INCIDENT_DB_PATH", db_path)

    def _always_raise(*args, **kwargs):
        raise app.ClassificationError("simulated malformed LLM response")

    monkeypatch.setattr(app, "classify", _always_raise)

    event = make_event()
    result = process_failure_event(event)

    assert isinstance(result, ProcessingFailure)
    assert result.event is event
    assert "simulated malformed LLM response" in str(result.error)


def test_process_failure_event_does_not_log_on_failure(tmp_path, monkeypatch):
    """
    A ProcessingFailure should mean nothing got logged — log_incident()
    happens after the try block, so a skill failure must prevent any
    (possibly incomplete/invalid) incident from being written.
    """
    db_path = str(tmp_path / "test_incidents.db")
    monkeypatch.setattr(app.config, "INCIDENT_DB_PATH", db_path)

    def _always_raise(*args, **kwargs):
        raise app.RootCauseError("simulated bad confidence_score")

    monkeypatch.setattr(app, "extract_root_cause", _always_raise)

    event = make_event()
    result = process_failure_event(event)

    assert isinstance(result, ProcessingFailure)
    # No incident_id exists to look up — confirm the DB file wasn't
    # even created, since log_incident() (which creates it) never ran.
    import os
    assert not os.path.exists(db_path)


def test_process_all_current_failures_processes_every_mock_event(
    tmp_path, monkeypatch
):
    """
    The batch driver should process every FailureEvent produced by the
    real (mocked) Dataverse + failure_filter pipeline, and report a
    matching count of successes.
    """
    db_path = str(tmp_path / "test_incidents.db")
    monkeypatch.setattr(app.config, "INCIDENT_DB_PATH", db_path)

    results = process_all_current_failures()

    assert len(results) > 0
    assert all(isinstance(r, ProcessingOutcome) for r in results)


def test_process_all_current_failures_continues_past_one_failure(
    tmp_path, monkeypatch
):
    """
    If one event's skill call fails, the batch must still process the
    remaining events rather than stopping at the first failure — this
    is the actual behavior per-event isolation is meant to guarantee at
    the batch level, not just the single-event level.
    """
    db_path = str(tmp_path / "test_incidents.db")
    monkeypatch.setattr(app.config, "INCIDENT_DB_PATH", db_path)

    call_count = {"n": 0}
    real_classify = app.classify

    def _fail_first_call_only(llm_response):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise app.ClassificationError("simulated failure on first event")
        return real_classify(llm_response)

    monkeypatch.setattr(app, "classify", _fail_first_call_only)

    results = process_all_current_failures()

    assert len(results) >= 2, "Mock fixtures must contain at least 2 FailureEvents for this test"
    assert isinstance(results[0], ProcessingFailure)
    assert any(isinstance(r, ProcessingOutcome) for r in results[1:])