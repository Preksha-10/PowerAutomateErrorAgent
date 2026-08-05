"""
dataverse_flows_tool — Foundry-Function-Tool-shaped wrapper around
DataverseClient.get_flows(). Directly callable in plain Python today;
shaped (typed input/output schema, single responsibility) so it can be
registered as an Azure AI Foundry Function Tool later with minimal
changes — just adding the tool schema decorator/registration, not
rewriting the logic.
"""

from dataclasses import dataclass, field
from typing import List

from services.dataverse_client import DataverseClient
from models.flow_record import FlowRecord


@dataclass
class GetActiveFlowsInput:
    """Typed input schema for this tool. Empty today (no parameters
    needed for mock mode), but kept as an explicit dataclass — not a
    bare function call with no args — so the Foundry Function Tool
    JSON schema has something concrete to describe, and so adding a
    parameter later (e.g. environment filter) doesn't change the
    tool's calling convention."""
    pass


@dataclass
class GetActiveFlowsOutput:
    """Typed output schema: only the flows that are actually
    monitored (Enabled). Filtering happens here, not in the caller,
    so every consumer of this tool gets pre-filtered data and never
    has to re-check is_monitored itself."""
    flows: List[FlowRecord] = field(default_factory=list)


def get_active_flows(client: DataverseClient) -> GetActiveFlowsOutput:
    """Tool entry point: retrieve all monitored (Enabled) flows.

    Client is passed in rather than constructed here — dependency
    injection keeps this function testable with a mock/fixture-backed
    client and swappable to a live client later with zero code change
    inside this function.
    """
    all_flows = client.get_flows()
    active = [f for f in all_flows if f.is_monitored]
    return GetActiveFlowsOutput(flows=active)