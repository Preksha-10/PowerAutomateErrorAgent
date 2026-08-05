"""
dataverse_exceptions_tool — Foundry-Function-Tool-shaped wrapper
around DataverseClient.get_exceptions(). Directly callable in plain
Python today; shaped for later registration as an Azure AI Foundry
Function Tool.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from services.dataverse_client import DataverseClient
from models.exception_record import ExceptionRecord


@dataclass
class GetFailedExceptionsInput:
    """Typed input schema. since is optional today (mock mode ignores
    it — the fixture file is small and static) but modeled now because
    live mode WILL require it: the master prompt's cost rule says
    exception queries must always be time-windowed, never an
    unbounded table scan. Keeping the parameter here means the tool's
    calling contract doesn't change when live mode lands."""
    since: Optional[datetime] = None


@dataclass
class GetFailedExceptionsOutput:
    """Typed output: only exceptions that are still active failures
    (status == Failed). Filtering happens here so every caller gets
    pre-filtered data and never re-checks is_active_failure itself —
    same pattern as dataverse_flows_tool's is_monitored filtering."""
    exceptions: List[ExceptionRecord] = field(default_factory=list)


def get_failed_exceptions(
    client: DataverseClient,
    params: Optional[GetFailedExceptionsInput] = None,
) -> GetFailedExceptionsOutput:
    """Tool entry point: retrieve all active (Failed) exceptions.

    params.since is accepted but not yet applied in mock mode —
    client.get_exceptions() has no time-window mechanism against a
    static fixture file. This is intentionally a no-op today rather
    than silently faked, so nothing here lies about what live mode
    will actually filter server-side via $filter.
    """
    params = params or GetFailedExceptionsInput()
    all_exceptions = client.get_exceptions()
    failed = [e for e in all_exceptions if e.is_active_failure]
    return GetFailedExceptionsOutput(exceptions=failed)