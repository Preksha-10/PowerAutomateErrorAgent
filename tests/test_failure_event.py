"""
tests/test_failure_event.py

Tests for the FailureEvent data model.
Verifies construction, defaults, and the LLM payload contract
(the cost-optimization boundary: exactly which fields reach the LLM).
"""

from datetime import datetime
from models.failure_event import FailureEvent


def make_sample_event() -> FailureEvent:
    """Helper: builds a consistent FailureEvent for use across tests."""
    return FailureEvent(
        flow_name="Invoice Approval Flow",
        environment="Production",
        action_name="Get Excel Rows",
        action_type="Excel",
        exception="FileLockedException",
        error_message="The file is locked by another process.",
        timestamp=datetime(2026, 1, 15, 9, 30, 0),
        machine_name="GATEWAY-VM-01",
    )


def test_failure_event_construction():
    """A FailureEvent should store all provided fields exactly as given."""
    event = make_sample_event()

    assert event.flow_name == "Invoice Approval Flow"
    assert event.environment == "Production"
    assert event.action_type == "Excel"
    assert event.machine_name == "GATEWAY-VM-01"


def test_screenshot_path_defaults_to_none():
    """screenshot_path is optional and should default to None when omitted."""
    event = make_sample_event()

    assert event.screenshot_path is None


def test_to_llm_payload_contains_expected_fields():
    """
    The LLM payload must contain exactly the fields your cost-optimization
    spec allows — nothing more. This test is the enforcement point: if
    someone later adds a field to to_llm_payload() that wasn't approved
    (e.g. accidentally including full flow JSON), this test documents
    and protects that boundary.
    """
    event = make_sample_event()
    payload = event.to_llm_payload()

    expected_keys = {
        "flow_name",
        "environment",
        "action_name",
        "action_type",
        "exception",
        "error_message",
        "timestamp",
        "machine_name",
        "has_screenshot",
    }

    assert set(payload.keys()) == expected_keys


def test_to_llm_payload_timestamp_is_string():
    """Timestamps must be serialized to ISO strings before reaching the LLM."""
    event = make_sample_event()
    payload = event.to_llm_payload()

    assert isinstance(payload["timestamp"], str)
    assert payload["timestamp"] == "2026-01-15T09:30:00"


def test_to_llm_payload_has_screenshot_false_when_none():
    """has_screenshot should be False when no screenshot_path was given."""
    event = make_sample_event()
    payload = event.to_llm_payload()

    assert payload["has_screenshot"] is False


def test_to_llm_payload_has_screenshot_true_when_provided():
    """has_screenshot should be True when a screenshot_path exists."""
    event = make_sample_event()
    event.screenshot_path = "C:\\logs\\screenshots\\failure_001.png"
    payload = event.to_llm_payload()

    assert payload["has_screenshot"] is True