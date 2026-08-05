"""
ExceptionRecord — typed internal representation of one row from
Dataverse's Exceptions/Errors table (assumed logical name:
cr_flowexceptions — TBD once validated via EntityDefinitions).

SCHEMA VALIDATION NOTE (must revisit once Dataverse access exists):
    Field names below are ASSUMPTIONS from the master prompt's
    "DATAVERSE DATA MODEL" section, same caveat as flow_record.py —
    verify real logical names via:
        GET [org]/api/data/v9.2/EntityDefinitions(LogicalName='cr_flowexceptions')?$expand=Attributes
    Only from_dataverse_dict's key lookups should need to change.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ExceptionStatus(str, Enum):
    """Mirrors Dataverse's Status choice column on the exception
    record. Only FAILED rows matter to failure_filter.py; the others
    exist so we can filter server-side with $filter instead of
    pulling everything and discarding client-side."""
    FAILED = "Failed"
    RESOLVED = "Resolved"
    RETRIED = "Retried"


@dataclass
class ExceptionRecord:
    """One exception/error row, as pulled from Dataverse's Exceptions
    table. Thin, flat mirror of the assumed schema — no join/dedupe
    logic here; that's skills/failure_filter.py's job once it has
    both this and a list of FlowRecord to cross-reference.
    """

    exception_id: str
    related_flow_id: str  # lookup field -> FlowRecord.flow_id
    run_id: str
    error_message: str
    exception_type: str
    action_name: str
    timestamp: datetime
    status: ExceptionStatus
    machine_name: Optional[str] = None  # PAD-only; Cloud Flows won't have this
    severity: Optional[str] = None      # optional pre-tagged severity, not always populated

    @property
    def is_active_failure(self) -> bool:
        """True only for unresolved failures. Kept as a derived
        property for the same reason as FlowRecord.is_monitored —
        centralizes the one business rule failure_filter.py needs
        ("is this exception something we still care about") so it's
        never re-implemented or drifted between callers.
        """
        return self.status == ExceptionStatus.FAILED

    @staticmethod
    def from_dataverse_dict(data: dict) -> "ExceptionRecord":
        """Single translation point from raw Dataverse-shaped dict
        (mock JSON today, parsed OData row later) to the typed model.
        Timestamp is parsed here so every caller downstream gets a
        real datetime, not a raw ISO string to re-parse repeatedly.
        """
        return ExceptionRecord(
            exception_id=data["exception_id"],
            related_flow_id=data["related_flow_id"],
            run_id=data["run_id"],
            error_message=data["error_message"],
            exception_type=data["exception_type"],
            action_name=data["action_name"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=ExceptionStatus(data["status"]),
            machine_name=data.get("machine_name"),
            severity=data.get("severity"),
        )