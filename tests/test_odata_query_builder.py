"""Tests for utils/odata_query_builder.py — pure string-building
functions, no network calls, no Dataverse access required."""

import pytest
from datetime import datetime

from utils.odata_query_builder import (
    build_select,
    build_status_filter,
    build_time_window_filter,
    combine_filters,
    build_expand,
    build_query_string,
)


def test_build_select_joins_fields():
    """Confirms the basic comma-joined shape Dataverse expects."""
    result = build_select(["cr_errormessage", "createdon"])
    assert result == "$select=cr_errormessage,createdon"


def test_build_select_rejects_empty_list():
    """Empty $select would mean 'pull everything' by omission — the
    master prompt treats that as a cost mistake, so this must fail
    loudly instead of silently building a useless clause."""
    with pytest.raises(ValueError):
        build_select([])


def test_build_status_filter_quotes_string_values():
    """String choice labels need single quotes per OData syntax."""
    result = build_status_filter("statuscode", "Failed")
    assert result == "statuscode eq 'Failed'"


def test_build_status_filter_does_not_quote_numeric_values():
    """Numeric choice values (the actual Dataverse choice-set
    integers) must NOT be quoted, or the query fails server-side."""
    result = build_status_filter("statuscode", "100000001")
    assert result == "statuscode eq 100000001"


def test_build_time_window_filter_formats_iso_utc():
    """Confirms the exact ISO-8601 'Z' format Dataverse's OData
    endpoint requires for datetime filters."""
    since = datetime(2025, 1, 1, 0, 0, 0)
    result = build_time_window_filter("createdon", since)
    assert result == "createdon ge 2025-01-01T00:00:00Z"


def test_combine_filters_defaults_to_and():
    """Status + time-window filters must combine with AND by default
    — this is the exact pattern the master prompt's example query uses."""
    result = combine_filters(["statuscode eq 100000001", "createdon ge 2025-01-01T00:00:00Z"])
    assert result == "$filter=statuscode eq 100000001 and createdon ge 2025-01-01T00:00:00Z"


def test_combine_filters_rejects_unsupported_operator():
    """Guards against a typo silently building an invalid OData clause."""
    with pytest.raises(ValueError):
        combine_filters(["a eq 1"], operator="xor")


def test_build_expand_with_nested_select():
    """Matches the master prompt's exact $expand example — pulling
    related Flow fields alongside an Exception in one round trip."""
    result = build_expand("cr_flowid", ["cr_flowname", "cr_environment", "statecode"])
    assert result == "$expand=cr_flowid($select=cr_flowname,cr_environment,statecode)"


def test_build_expand_without_select():
    """$expand is still valid without a nested $select, just pulls
    all fields of the related entity — less common but supported."""
    result = build_expand("cr_flowid")
    assert result == "$expand=cr_flowid"


def test_build_query_string_joins_with_ampersand():
    """Confirms the final assembly step produces a URL-appendable
    query string in the right shape."""
    result = build_query_string(["$select=a,b", "$filter=x eq 1"])
    assert result == "$select=a,b&$filter=x eq 1"