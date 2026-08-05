"""Tests for tools/dataverse_exceptions_tool.py — mock DataverseClient
via fixture files, no network calls."""

import json
import pytest

from services.dataverse_client import DataverseClient
from tools.dataverse_exceptions_tool import (
    get_failed_exceptions,
    GetFailedExceptionsInput,
    GetFailedExceptionsOutput,
)


@pytest.fixture
def client_with_mixed_exceptions(tmp_path):
    exceptions_data = [
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
        },
        {
            "exception_id": "e-2",
            "related_flow_id": "f-1",
            "run_id": "r-2",
            "error_message": "Timeout",
            "exception_type": "Timeout",
            "action_name": "Wait For Response",
            "timestamp": "2025-01-01T11:00:00",
            "status": "Resolved",
        },
    ]
    flows_path = tmp_path / "mock_flows.json"
    exceptions_path = tmp_path / "mock_exceptions.json"
    flows_path.write_text(json.dumps([]))
    exceptions_path.write_text(json.dumps(exceptions_data))
    return DataverseClient(
        mode="mock",
        flows_fixture_path=str(flows_path),
        exceptions_fixture_path=str(exceptions_path),
    )


def test_get_failed_exceptions_returns_only_failed_status(client_with_mixed_exceptions):
    """Confirms the tool's core contract: callers only ever see active
    (Failed) exceptions, never Resolved/Retried ones — this is what
    failure_filter.py depends on to avoid re-processing handled incidents."""
    result = get_failed_exceptions(client_with_mixed_exceptions)
    assert isinstance(result, GetFailedExceptionsOutput)
    assert len(result.exceptions) == 1
    assert result.exceptions[0].exception_id == "e-1"


def test_get_failed_exceptions_accepts_since_param_without_error(client_with_mixed_exceptions):
    """The since parameter must be accepted today even though mock
    mode doesn't apply it yet — this locks in the calling contract so
    orchestration code written now doesn't break when live mode
    starts actually honoring the time window."""
    from datetime import datetime
    params = GetFailedExceptionsInput(since=datetime(2025, 1, 1))
    result = get_failed_exceptions(client_with_mixed_exceptions, params)
    assert len(result.exceptions) == 1


def test_get_failed_exceptions_returns_empty_list_when_none_failed(tmp_path):
    """All-resolved exceptions should produce an empty list, not an
    error — downstream orchestration should treat 'nothing new failed'
    as a normal, expected outcome."""
    exceptions_data = [
        {
            "exception_id": "e-3",
            "related_flow_id": "f-1",
            "run_id": "r-3",
            "error_message": "Fixed on retry",
            "exception_type": "Timeout",
            "action_name": "Wait For Response",
            "timestamp": "2025-01-01T12:00:00",
            "status": "Retried",
        }
    ]
    flows_path = tmp_path / "mock_flows.json"
    exceptions_path = tmp_path / "mock_exceptions.json"
    flows_path.write_text(json.dumps([]))
    exceptions_path.write_text(json.dumps(exceptions_data))
    client = DataverseClient(
        mode="mock",
        flows_fixture_path=str(flows_path),
        exceptions_fixture_path=str(exceptions_path),
    )
    result = get_failed_exceptions(client)
    assert result.exceptions == []