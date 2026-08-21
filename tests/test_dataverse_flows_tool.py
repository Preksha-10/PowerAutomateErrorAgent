"""Tests for tools/dataverse_flows_tool.py — mock DataverseClient via
fixture files, no network calls."""

import json
import pytest  # type: ignore[reportMissingImports]

from services.dataverse_client import DataverseClient
from tools.dataverse_flows_tool import (
    TOOL_SCHEMA,
    execute_tool_call,
    get_active_flows,
    GetActiveFlowsOutput,
)


@pytest.fixture
def client_with_mixed_flows(tmp_path):


    flows_data = [
        {
            "flow_id": "f-1",
            "flow_name": "Invoice Sync",
            "environment": "Production",
            "owner": "finance-team@example.com",
            "status": "Enabled",
            "flow_type": "Cloud",
        },
        {
            "flow_id": "f-2",
            "flow_name": "Legacy SAP Extract",
            "environment": "Production",
            "owner": "ops-team@example.com",
            "status": "Disabled",
            "flow_type": "Desktop",
        },
    ]
    exceptions_data = []  # not used by this tool, but client needs a valid path
    flows_path = tmp_path / "mock_flows.json"
    exceptions_path = tmp_path / "mock_exceptions.json"
    flows_path.write_text(json.dumps(flows_data))
    exceptions_path.write_text(json.dumps(exceptions_data))
    return DataverseClient(
        mode="mock",
        flows_fixture_path=str(flows_path),
        exceptions_fixture_path=str(exceptions_path),
    )


def test_get_active_flows_returns_only_enabled(client_with_mixed_flows):


    """Confirms the tool's core contract: callers only ever see
    monitored flows, never disabled/retired ones — this is what
    failure_filter.py depends on to discard exceptions from
    unmonitored flows without re-checking status itself."""
    result = get_active_flows(client_with_mixed_flows)
    assert isinstance(result, GetActiveFlowsOutput)
    assert len(result.flows) == 1
    assert result.flows[0].flow_id == "f-1"


def test_get_active_flows_returns_empty_list_when_none_enabled(tmp_path):


    """No enabled flows should produce an empty list, not an error —
    downstream code (failure_filter) should handle 'nothing to
    monitor right now' gracefully rather than crashing."""
    flows_data = [
        {
            "flow_id": "f-9",
            "flow_name": "Fully Retired Flow",
            "environment": "Production",
            "owner": "someone@example.com",
            "status": "Disabled",
            "flow_type": "Cloud",
        }
    ]
    flows_path = tmp_path / "mock_flows.json"
    exceptions_path = tmp_path / "mock_exceptions.json"
    flows_path.write_text(json.dumps(flows_data))
    exceptions_path.write_text(json.dumps([]))
    client = DataverseClient(
        mode="mock",
        flows_fixture_path=str(flows_path),
        exceptions_fixture_path=str(exceptions_path),
    )
    result = get_active_flows(client)
    assert result.flows == []

def test_get_active_flows_tool_schema():


    """The Foundry function schema exposes the correct tool contract."""

    assert TOOL_SCHEMA["type"] == "function"

    function_schema = TOOL_SCHEMA["function"]

    assert function_schema["name"] == "get_active_flows"
    assert function_schema["parameters"]["type"] == "object"
    assert function_schema["parameters"]["properties"] == {}
    assert function_schema["parameters"]["required"] == []

def test_mock_foundry_tool_call_executes_get_active_flows(
    client_with_mixed_flows,
):


    """
    Simulates the payload an Agent would provide when requesting
    the get_active_flows function tool.

    No real Azure Foundry Agent or network call is performed.
    """

    tool_call = {
        "name": "get_active_flows",
        "arguments": {},
    }

    result = execute_tool_call(
        tool_name=tool_call["name"],
        arguments=tool_call["arguments"],
        client=client_with_mixed_flows,
    )

    assert result == {
        "flows": [
            {
                "flow_id": "f-1",
                "flow_name": "Invoice Sync",
                "environment": "Production",
                "owner": "finance-team@example.com",
                "status": "Enabled",
                "flow_type": "Cloud",
            }
        ]
    }

def test_get_active_flows_rejects_arguments(
    client_with_mixed_flows,
):


    with pytest.raises(ValueError, match="does not accept"):
        execute_tool_call(
            tool_name="get_active_flows",
            arguments={"environment": "Production"},
            client=client_with_mixed_flows,
        )

def test_unknown_tool_is_rejected(
    client_with_mixed_flows,
):


    with pytest.raises(ValueError, match="Unknown tool"):
        execute_tool_call(
            tool_name="unknown_tool",
            arguments={},
            client=client_with_mixed_flows,
        )
