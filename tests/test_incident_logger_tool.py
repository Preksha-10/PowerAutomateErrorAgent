"""
tests/test_incident_logger_tool.py

Tests for tools/incident_logger_tool.py.
Verifies logging returns a usable incident_id, that a logged incident
can be retrieved with its data intact, that mark_processed() correctly
flips the processed flag and reports found/not-found, and that
get_incident() returns None (not an exception) for an unknown ID.

Uses pytest's tmp_path fixture for every db_path, so these tests never
read or write a real database file.
"""

from datetime import datetime, timezone

from models.incident_report import ErrorCategory, IncidentReport, Severity
from tools.incident_logger_tool import get_incident, log_incident, mark_processed


def make_sample_report(**overrides) -> IncidentReport:
    """Helper: builds a consistent IncidentReport for logger tests."""
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


def test_log_incident_returns_a_usable_incident_id(tmp_path):
    """log_incident() should return a non-empty string ID that can be
    used to look the record back up."""
    db_path = str(tmp_path / "test_incidents.db")
    report = make_sample_report()

    incident_id = log_incident(report, db_path=db_path)

    assert isinstance(incident_id, str)
    assert len(incident_id) > 0


def test_logged_incident_can_be_retrieved_with_data_intact(tmp_path):
    """A logged incident, when retrieved, should contain the same field
    values it was stored with."""
    db_path = str(tmp_path / "test_incidents.db")
    report = make_sample_report()

    incident_id = log_incident(report, db_path=db_path)
    retrieved = get_incident(incident_id, db_path=db_path)

    assert retrieved is not None
    assert retrieved["flow_name"] == "Invoice Approval Flow"
    assert retrieved["severity"] == "High"
    assert retrieved["error_category"] == "Excel Locked/Missing"


def test_logged_incident_starts_unprocessed(tmp_path):
    """A freshly logged incident should be marked unprocessed until
    mark_processed() is explicitly called."""
    db_path = str(tmp_path / "test_incidents.db")
    report = make_sample_report()

    incident_id = log_incident(report, db_path=db_path)
    retrieved = get_incident(incident_id, db_path=db_path)

    assert retrieved["processed"] is False


def test_mark_processed_flips_the_flag(tmp_path):
    """After mark_processed(), the retrieved incident's processed field
    should be True, and mark_processed() itself should report success."""
    db_path = str(tmp_path / "test_incidents.db")
    report = make_sample_report()
    incident_id = log_incident(report, db_path=db_path)

    was_found = mark_processed(incident_id, db_path=db_path)
    retrieved = get_incident(incident_id, db_path=db_path)

    assert was_found is True
    assert retrieved["processed"] is True


def test_mark_processed_returns_false_for_unknown_id(tmp_path):
    """Calling mark_processed() with an ID that was never logged should
    return False, not raise — this is how a caller detects a bad/stale
    incident_id."""
    db_path = str(tmp_path / "test_incidents.db")

    was_found = mark_processed("not-a-real-id", db_path=db_path)

    assert was_found is False


def test_get_incident_returns_none_for_unknown_id(tmp_path):
    """A lookup for an ID that doesn't exist should return None, since
    'not found' is an expected outcome for a lookup, not an error."""
    db_path = str(tmp_path / "test_incidents.db")

    result = get_incident("not-a-real-id", db_path=db_path)

    assert result is None


def test_multiple_incidents_get_distinct_ids(tmp_path):
    """Logging two different reports should produce two distinct
    incident_ids, each independently retrievable."""
    db_path = str(tmp_path / "test_incidents.db")
    report_a = make_sample_report(flow_name="Flow A")
    report_b = make_sample_report(flow_name="Flow B")

    id_a = log_incident(report_a, db_path=db_path)
    id_b = log_incident(report_b, db_path=db_path)

    assert id_a != id_b
    assert get_incident(id_a, db_path=db_path)["flow_name"] == "Flow A"
    assert get_incident(id_b, db_path=db_path)["flow_name"] == "Flow B"


def test_db_directory_is_created_automatically(tmp_path):
    """log_incident() should create any missing parent directories for
    db_path (e.g. a fresh checkout with no temp/ folder yet) rather than
    raising a FileNotFoundError."""
    nested_db_path = str(tmp_path / "nested" / "does_not_exist_yet" / "incidents.db")
    report = make_sample_report()

    incident_id = log_incident(report, db_path=nested_db_path)

    assert get_incident(incident_id, db_path=nested_db_path) is not None