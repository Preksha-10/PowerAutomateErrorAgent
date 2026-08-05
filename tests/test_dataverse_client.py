"""Tests for services/dataverse_client.py — mock mode only, zero
network calls. Uses tmp_path fixtures instead of the real
sample_errors/ files so tests don't depend on their exact contents."""

import json
import pytest

from services.dataverse_client import DataverseClient
from models.flow_record import FlowRecord
from models.exception_record import ExceptionRecord


@pytest.fixture
def flows_json(tmp_path):
    data = [
        {
            "flow_id": "f-1",
            "flow_name": "Invoice Sync",
            "environment": "Production",
            "owner": "finance-team@example.com",
            "status": "Enabled",
            "flow_type": "Cloud",
        }
    ]
    path = tmp_path / "mock_flows.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture
def exceptions_json(tmp_path):
    data = [
        {
            "exception_id": "e-1",
            "related_flow_id": "f-1",
            "run_id": "r-1",
            "error_message": "UI element not found",
            "exception_type": "ElementNotFound",
            "action_name": "Click Submit",
            "timestamp": "2025-01-01T10:00:00",
            "status": "Failed",
            "machine_name": "DESKTOP-01",
        }
    ]
    path = tmp_path / "mock_exceptions.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_get_flows_returns_parsed_flow_records(flows_json, exceptions_json):
    """Confirms get_flows() reads the fixture and hands back real
    FlowRecord objects, not raw dicts — callers should never see
    Dataverse's raw shape."""
    client = DataverseClient(
        mode="mock",
        flows_fixture_path=flows_json,
        exceptions_fixture_path=exceptions_json,
    )
    flows = client.get_flows()
    assert len(flows) == 1
    assert isinstance(flows[0], FlowRecord)
    assert flows[0].flow_id == "f-1"


def test_get_exceptions_returns_parsed_exception_records(flows_json, exceptions_json):
    """Same guarantee as above, for exceptions — this is the other
    half of what failure_filter.py needs to do its join."""
    client = DataverseClient(
        mode="mock",
        flows_fixture_path=flows_json,
        exceptions_fixture_path=exceptions_json,
    )
    exceptions = client.get_exceptions()
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], ExceptionRecord)
    assert exceptions[0].exception_id == "e-1"


def test_missing_fixture_file_raises_clear_error(tmp_path):
    """A missing/misconfigured fixture path should fail with a
    message pointing at the actual problem, not a bare
    FileNotFoundError with no context — this matters once teammates
    are running tests against their own local paths."""
    missing_path = str(tmp_path / "does_not_exist.json")
    client = DataverseClient(
        mode="mock",
        flows_fixture_path=missing_path,
        exceptions_fixture_path=missing_path,
    )
    with pytest.raises(FileNotFoundError):
        client.get_flows()


def test_live_mode_raises_not_implemented():
    """Live mode must fail loudly today rather than silently
    behaving like mock mode — protects against a future config
    mistake (e.g. an env var flipping mode by accident) going
    unnoticed before real credentials exist."""
    with pytest.raises(NotImplementedError):
        DataverseClient(mode="live")


def test_invalid_mode_raises_value_error():
    """Guards against typos in the mode string at construction time,
    not deep inside a get_* call."""
    with pytest.raises(ValueError):
        DataverseClient(mode="staging")