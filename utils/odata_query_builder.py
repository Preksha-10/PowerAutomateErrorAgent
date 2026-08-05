"""
odata_query_builder — pure functions that construct OData v4 query
string fragments ($filter, $select, $expand) for Dataverse Web API
calls, per the patterns in the master prompt.

DESIGN INTENT: these are pure string-building functions with zero
network/SDK dependencies, so they're fully unit-testable without
Dataverse access and reusable from dataverse_client.py once live mode
is implemented. No caller should ever hand-write an OData query
string directly — always go through here so filter-injection mistakes
(e.g. unescaped quotes) are caught in one place.
"""

from datetime import datetime
from typing import List, Optional


def build_select(fields: List[str]) -> str:
    """Build a $select clause. Enforced non-empty because pulling all
    columns is a cost mistake the master prompt explicitly warns
    against — every query must be deliberate about which fields it
    needs."""
    if not fields:
        raise ValueError("$select requires at least one field — never pull all columns.")
    return "$select=" + ",".join(fields)


def build_status_filter(status_field: str, status_value: str) -> str:
    """Build a simple equality filter, e.g. statuscode eq 100000001.
    String values are wrapped in single quotes per OData syntax;
    numeric/choice values are not. Caller passes the already-correct
    literal (e.g. "100000001" for a choice value, or "'Enabled'" is
    NOT expected — pass "Enabled" and this function quotes it only
    when it's not purely numeric).
    """
    if not status_field or not status_value:
        raise ValueError("status_field and status_value are required")
    if status_value.isdigit():
        return f"{status_field} eq {status_value}"
    return f"{status_field} eq '{status_value}'"


def build_time_window_filter(timestamp_field: str, since: datetime) -> str:
    """Build a createdon-style filter for 'records since a given
    time', e.g. createdon ge 2025-01-01T00:00:00Z. This is what
    replaces polling — we always bound exception queries by time
    window, never fetch the entire table."""
    if not timestamp_field:
        raise ValueError("timestamp_field is required")
    iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{timestamp_field} ge {iso}"


def combine_filters(filters: List[str], operator: str = "and") -> str:
    """Combine multiple filter fragments into one $filter clause.
    Kept separate from the individual builders so callers can compose
    status + time-window (or any future filters) without this module
    needing to know every possible combination in advance."""
    if not filters:
        raise ValueError("combine_filters requires at least one filter fragment")
    if operator not in ("and", "or"):
        raise ValueError(f"Unsupported operator: {operator}")
    joined = f" {operator} ".join(filters)
    return f"$filter={joined}"


def build_expand(
    navigation_property: str,
    select_fields: Optional[List[str]] = None,
) -> str:
    """Build a $expand clause, e.g.
    $expand=cr_flowid($select=cr_flowname,cr_environment,statecode)
    used to pull the related Flow's fields alongside an Exception
    record in one round trip instead of a second query."""
    if not navigation_property:
        raise ValueError("navigation_property is required")
    if select_fields:
        inner = ",".join(select_fields)
        return f"$expand={navigation_property}($select={inner})"
    return f"$expand={navigation_property}"


def build_query_string(clauses: List[str]) -> str:
    """Join already-built clauses ($select=..., $filter=..., etc.)
    into a single query string with '&', ready to append to a base
    Dataverse entity URL. Doesn't validate ordering — Dataverse
    doesn't require a specific clause order — just joins what it's given."""
    if not clauses:
        raise ValueError("build_query_string requires at least one clause")
    return "&".join(clauses)