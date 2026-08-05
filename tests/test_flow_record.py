"""Tests for models/flow_record.py — no network calls, no Dataverse
access required. Uses in-memory dicts shaped like mock Dataverse rows."""

import pytest

from models.flow_record import FlowRecord, FlowStatus, FlowType


def test_is_monitored_true_for_enabled_flow():
    """An Enabled flow must be treated as monitored — this is the
    single business rule the whole detection pipeline hinges on for
    deciding which exceptions even matter."""
    flow = FlowRecord(
        flow_id="f-1",
        flow_name="Invoice Sync",
        environment="Production",
        owner="finance-team@example.com",
        status=FlowStatus.ENABLED,
        flow_type=FlowType.CLOUD,
    )
    assert flow.is_monitored is True


def test_is_monitored_false_for_disabled_flow():
    """A Disabled flow must NOT be monitored, even if it still has
    stale exception records sitting in Dataverse — failure_filter.py
    relies on this to discard noise from retired flows."""
    flow = FlowRecord(
        flow_id="f-2",
        flow_name="Legacy SAP Extract",
        environment="Production",
        owner="ops-team@example.com",
        status=FlowStatus.DISABLED,
        flow_type=FlowType.DESKTOP,
    )
    assert flow.is_monitored is False


def test_from_dataverse_dict_builds_matching_record():
    """from_dataverse_dict is the single translation seam between raw
    Dataverse-shaped data and our typed model — this locks in that the
    mapping is correct today, giving a clear regression check for later."""
    raw = {
        "flow_id": "f-3",
        "flow_name": "PO Approval",
        "environment": "UAT",
        "owner": "procurement@example.com",
        "status": "Enabled",
        "flow_type": "Cloud",
    }
    flow = FlowRecord.from_dataverse_dict(raw)
    assert flow.flow_id == "f-3"
    assert flow.status == FlowStatus.ENABLED
    assert flow.flow_type == FlowType.CLOUD
    assert flow.is_monitored is True


def test_from_dataverse_dict_rejects_unknown_status():
    """If Dataverse ever hands back a status value outside our known
    enum (schema drift, typo in choice set), we want a loud failure
    here rather than a silently wrong is_monitored result downstream."""
    raw = {
        "flow_id": "f-4",
        "flow_name": "Unknown Status Flow",
        "environment": "Production",
        "owner": "someone@example.com",
        "status": "Archived",
        "flow_type": "Cloud",
    }
    with pytest.raises(ValueError):
        FlowRecord.from_dataverse_dict(raw)