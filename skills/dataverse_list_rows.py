"""
skills/dataverse_list_rows.py

Small helper skill exposing Dataverse "list rows" style helpers for
flows and exceptions. These intentionally delegate to the existing
tools (dataverse_flows_tool, dataverse_exceptions_tool) so the
call-signature and filtering logic remain centralized and testable.
"""

from datetime import datetime
from typing import List, Optional

from services.dataverse_client import DataverseClient
from models.flow_record import FlowRecord
from models.exception_record import ExceptionRecord


def list_active_flows(client: DataverseClient) -> List[FlowRecord]:
    """Return monitored/active flows using the existing tool logic.

    Args:
        client: DataverseClient instance (injected for testability).

    Returns:
        List of `FlowRecord` objects that are monitored/active.
    """
    # Import locally to avoid import cycles at module import time.
    from tools.dataverse_flows_tool import get_active_flows

    output = get_active_flows(client)
    return output.flows


def list_failed_exceptions(
    client: DataverseClient, since: Optional[datetime] = None
) -> List[ExceptionRecord]:
    """Return active/failed exceptions, optionally time-windowed.

    Args:
        client: DataverseClient instance (injected for testability).
        since: optional datetime to request exceptions since that time.

    Returns:
        List of `ExceptionRecord` objects that represent active failures.
    """
    from tools.dataverse_exceptions_tool import (
        get_failed_exceptions,
        GetFailedExceptionsInput,
    )

    params = GetFailedExceptionsInput(since=since) if since is not None else None
    output = get_failed_exceptions(client, params)
    return output.exceptions
