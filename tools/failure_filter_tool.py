"""
Foundry Function Tool wrapper around skills.failure_filter.

The underlying failure_filter remains a pure Python skill.
This module only exposes its capability through a typed
Agent-facing function-tool contract.
"""

from typing import Any

from models.flow_record import FlowRecord
from models.exception_record import ExceptionRecord
from skills.failure_filter import filter_and_join


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "filter_failure_events",
        "description": (
            "Joins monitored Power Automate flows with failed "
            "exceptions, removes exceptions belonging to "
            "unmonitored flows, deduplicates retry chains, and "
            "returns normalized failure events."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "flows": {
                    "type": "array",
                    "description": "Flow records retrieved from Dataverse.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flow_id": {"type": "string"},
                            "flow_name": {"type": "string"},
                            "environment": {"type": "string"},
                            "owner": {"type": "string"},
                            "status": {"type": "string"},
                            "flow_type": {"type": "string"},
                        },
                        "required": [
                            "flow_id",
                            "flow_name",
                            "environment",
                            "owner",
                            "status",
                            "flow_type",
                        ],
                    },
                },
                "exceptions": {
                    "type": "array",
                    "description": "Failed exception records from Dataverse.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "exception_id": {"type": "string"},
                            "related_flow_id": {"type": "string"},
                            "run_id": {"type": "string"},
                            "error_message": {"type": "string"},
                            "exception_type": {"type": "string"},
                            "action_name": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "status": {"type": "string"},
                            "machine_name": {"type": "string"},
                        },
                        "required": [
                            "exception_id",
                            "related_flow_id",
                            "run_id",
                            "error_message",
                            "exception_type",
                            "action_name",
                            "timestamp",
                            "status",
                        ],
                    },
                },
            },
            "required": ["flows", "exceptions"],
        },
    },
}

def execute_tool_call(
    tool_name: str,
    arguments: dict,
) -> dict:
    """Execute the failure-filter capability from Agent JSON input."""

    if tool_name != TOOL_SCHEMA["function"]["name"]:
        raise ValueError(f"Unknown tool: {tool_name}")

    if set(arguments) != {"flows", "exceptions"}:
        raise ValueError(
            "filter_failure_events requires flows and exceptions"
        )

    flows = [
        FlowRecord.model_validate(flow)
        for flow in arguments["flows"]
    ]

    exceptions = [
        ExceptionRecord.model_validate(exception)
        for exception in arguments["exceptions"]
    ]

    failure_events = filter_and_join(flows, exceptions)

    return {
        "failure_events": [
            event.model_dump(mode="json")
            for event in failure_events
        ]
    }