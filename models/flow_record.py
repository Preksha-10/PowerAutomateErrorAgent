"""
FlowRecord — typed internal representation of one row from Dataverse's
Flows table (assumed logical name: cr_flows, or the built-in Power
Automate flow entity — TBD once we validate via EntityDefinitions).

SCHEMA VALIDATION NOTE (must revisit once Dataverse access exists):
    Every field name below is an ASSUMPTION taken directly from the
    master prompt's "DATAVERSE DATA MODEL" section. Real Dataverse
    logical/schema names almost never match display names 1:1 (e.g.
    "Flow Name" is very likely something like cr_flowname, not
    "flow_name"). Before wiring services/dataverse_client.py to live
    mode, hit:
        GET [org]/api/data/v9.2/EntityDefinitions(LogicalName='cr_flows')?$expand=Attributes
    and update the mapping in dataverse_client.py's live-mode transport
    (NOT this file's field names, unless real types genuinely differ).
"""

from dataclasses import dataclass
from enum import Enum


class FlowStatus(str, Enum):
    """Mirrors Dataverse's Status choice column. String enum so it
    serializes cleanly into dicts/JSON fixtures without a custom encoder."""
    ENABLED = "Enabled"
    DISABLED = "Disabled"


class FlowType(str, Enum):
    """Cloud vs Desktop (PAD) — drives which failure-category branch
    the classifier skill takes downstream."""
    CLOUD = "Cloud"
    DESKTOP = "Desktop"


@dataclass
class FlowRecord:
    """One monitored flow, as pulled from Dataverse's Flows table.

    Intentionally a thin, flat mirror of the assumed schema — no
    business logic lives here. Filtering/joining logic belongs in
    skills/failure_filter.py, which consumes lists of these.
    """

    flow_id: str
    flow_name: str
    environment: str
    owner: str
    status: FlowStatus
    flow_type: FlowType

    @property
    def is_monitored(self) -> bool:
        """True if this flow should be considered for failure
        detection at all. Kept as a derived property (not a stored
        field) because "monitored" is a business rule — currently
        just status == Enabled — not a fact Dataverse hands us
        directly. Centralizing it here means failure_filter.py never
        re-implements it, and if the rule grows it changes in one place.
        """
        return self.status == FlowStatus.ENABLED

    @staticmethod
    def from_dataverse_dict(data: dict) -> "FlowRecord":
        """Construct a FlowRecord from a raw Dataverse-shaped dict
        (today: a mock JSON fixture; later: a parsed OData response
        row). Single translation point — when real Dataverse field
        names differ from our assumptions, only this method changes;
        every caller keeps using clean FlowRecord attribute names.
        """
        return FlowRecord(
            flow_id=data["flow_id"],
            flow_name=data["flow_name"],
            environment=data["environment"],
            owner=data["owner"],
            status=FlowStatus(data["status"]),
            flow_type=FlowType(data["flow_type"]),
        )