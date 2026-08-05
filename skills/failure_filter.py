"""
failure_filter — joins FlowRecord + ExceptionRecord, discards
exceptions belonging to unmonitored/disabled flows, and dedupes
retry chains (same run's exception logged multiple times) into one
FailureEvent per real incident.

IMPORTANT ASSUMPTION FLAG:
    This reuses models/failure_event.py's existing FailureEvent class
    (per your instruction — not redefining it), but I don't have that
    file's actual field list/constructor in front of me — only the
    field names mentioned in the work-split doc: flow_name,
    environment, action_name, action_type, exception, error_message,
    timestamp, machine_name, screenshot_path.
    Two of those don't have an obvious 1:1 source in FlowRecord/
    ExceptionRecord as built so far:
      - action_type: no such field exists yet on either model. Mapped
        below to FlowRecord.flow_type.value (Cloud/Desktop) as the
        closest available signal — CONFIRM this is what FailureEvent
        actually expects, or tell me the real intent and I'll adjust.
      - exception: mapped to ExceptionRecord.exception_type.
      - screenshot_path: no source exists yet (PAD-only, not modeled
        on ExceptionRecord) — passed as None for now.
    If FailureEvent's real constructor signature differs from what's
    assumed here, only the _to_failure_event() function below needs
    to change — paste the real file and I'll fix it in one pass.
"""

from collections import defaultdict
from typing import List

from models.flow_record import FlowRecord
from models.exception_record import ExceptionRecord
from models.failure_event import FailureEvent


def filter_and_join(
    flows: List[FlowRecord],
    exceptions: List[ExceptionRecord],
) -> List[FailureEvent]:
    """Main entry point: joins active exceptions to their monitored
    flow, discards anything that doesn't resolve to a monitored flow,
    dedupes retry chains, and returns one FailureEvent per real
    incident.

    Kept as a single pure function (no I/O, no client) so it's
    trivially unit-testable with hand-built lists — no mocking needed.
    """
    monitored_flows_by_id = {f.flow_id: f for f in flows if f.is_monitored}

    active_exceptions = [e for e in exceptions if e.is_active_failure]

    # Discard exceptions whose flow isn't monitored (disabled, or not
    # found at all — e.g. deleted flow with orphaned exception rows).
    joinable = [
        e for e in active_exceptions if e.related_flow_id in monitored_flows_by_id
    ]

    deduped = _dedupe_retry_chains(joinable)

    return [
        _to_failure_event(exc, monitored_flows_by_id[exc.related_flow_id], retry_count)
        for exc, retry_count in deduped
    ]


def _dedupe_retry_chains(exceptions: List[ExceptionRecord]):
    """Collapse multiple exception rows from the same run's retry
    chain into one — keep the latest (by timestamp) per run_id, note
    how many rows collapsed into it as the retry count.

    Grouping by run_id (not exception_id) is the key decision: a
    single logical run that retries 3 times before failing for good
    produces 3 exception rows sharing one run_id, and we only want to
    alert on that once.
    """
    by_run_id = defaultdict(list)
    for exc in exceptions:
        by_run_id[exc.run_id].append(exc)

    result = []
    for run_id, group in by_run_id.items():
        latest = max(group, key=lambda e: e.timestamp)
        retry_count = len(group) - 1  # 0 if it failed on first attempt
        result.append((latest, retry_count))
    return result


def _to_failure_event(
    exc: ExceptionRecord,
    flow: FlowRecord,
    retry_count: int,
) -> FailureEvent:
    """Single translation point from (ExceptionRecord, FlowRecord) ->
    FailureEvent. machine_name is required (str) on FailureEvent but
    Optional on ExceptionRecord (Cloud Flow exceptions have none) —
    falls back to "N/A" rather than passing None into a non-optional field.
    """
    return FailureEvent(
        flow_name=flow.flow_name,
        environment=flow.environment,
        action_name=exc.action_name,
        action_type=flow.flow_type.value,
        exception=exc.exception_type,
        error_message=exc.error_message,
        timestamp=exc.timestamp,
        machine_name=exc.machine_name or "N/A",
        screenshot_path=None,
    )