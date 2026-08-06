"""
app.py — Orchestrator entry point for the Power Automate Failure
Detection AI Agent.

STATUS: Phase 2 orchestrator — mock mode, real logic.

This wires together both Phase 1 tracks into one working pipeline:

    Data & Ingestion:  DataverseClient -> Flows/Exceptions tools
                        -> failure_filter.filter_and_join()
    Reasoning & Output: ONE shared LLM call (utils.llm_stub today)
                        -> four extraction skills -> IncidentReport
                        -> notification_tool + incident_logger_tool

Entry points:
    process_failure_event(event)     — the per-event pipeline. This is
        the function a real Dataverse trigger will eventually call once
        per new Exception record (today: called in a loop over every
        currently-failed exception, since there's no live trigger yet).

    process_all_current_failures()   — mock-mode batch driver: fetches
        everything currently failed and processes each one, isolating
        failures so one bad event doesn't stop the rest.

Still NOT done (deliberately, not an oversight):
    - No real Dataverse trigger — live mode raises NotImplementedError
      inside DataverseClient itself; this file doesn't work around that.
    - No retry/dead-letter handling for a skipped event — see
      ProcessingFailure below; deciding what to do with these is a
      later, informed decision once real failure patterns are observed.
    - No real LLM call — utils.llm_stub.get_stub_response() stands in;
      swapping it for a real Azure AI Foundry call touches only that
      one file, per its own module docstring.
"""

import logging
from dataclasses import dataclass
from typing import List, Union

from pydantic import ValidationError

import config
from models.failure_event import FailureEvent
from models.incident_report import IncidentReport
from services.dataverse_client import DataverseClient
from skills.classifier import ClassificationError, classify
from skills.failure_filter import filter_and_join
from skills.fix_recommendation import FixRecommendationError, extract_fix_recommendation
from skills.root_cause import RootCauseError, extract_root_cause
from skills.summarizer import SummaryError, extract_summary
from tools.dataverse_exceptions_tool import get_failed_exceptions
from tools.dataverse_flows_tool import get_active_flows
from tools.incident_logger_tool import log_incident, mark_processed
from tools.notification_tool import NotificationChannel, NotificationResult, send_notification
from utils.llm_stub import get_stub_response

logger = logging.getLogger("power_automate_error_agent.orchestrator")


@dataclass
class ProcessingOutcome:
    """Successful result of processing one FailureEvent end to end."""

    incident_id: str
    report: IncidentReport
    notification_results: List[NotificationResult]


@dataclass
class ProcessingFailure:
    """
    Failed result of processing one FailureEvent.

    A separate type from ProcessingOutcome, not a shared type with an
    optional error field — a caller checking isinstance() is unambiguous,
    where a nullable-everything dataclass invites forgetting to check
    which fields are actually populated.
    """

    event: FailureEvent
    error: Exception


def process_failure_event(
    event: FailureEvent,
) -> Union[ProcessingOutcome, ProcessingFailure]:
    """
    Runs the full pipeline for a single FailureEvent: one shared LLM
    call, four extraction skills, IncidentReport assembly, logging,
    then notification.

    Log-before-notify is deliberate: the incident record must exist
    durably BEFORE a best-effort notification is attempted. If
    notification fails (a real Teams/Graph API outage, later), the
    incident is still permanently recorded and can be found by anyone
    looking it up — the reverse order would risk alerting about an
    incident that was never actually saved anywhere.

    Returns a ProcessingOutcome on success, or a ProcessingFailure
    (never raises) if any of the four reasoning skills or IncidentReport
    construction itself fails — letting a batch caller isolate one bad
    event from the rest rather than aborting entirely.
    """
    try:
        # One shared LLM call — every skill below extracts from THIS
        # single response. See skills/classifier.py's module docstring
        # for why this matters for the project's cost rule.
        payload = event.to_llm_payload()
        llm_response = get_stub_response(payload)

        category, severity = classify(llm_response)
        root_cause = extract_root_cause(llm_response)
        summary = extract_summary(llm_response)
        fix = extract_fix_recommendation(llm_response)

        report = IncidentReport(
            flow_name=event.flow_name,
            environment=event.environment,
            machine_name=event.machine_name,
            timestamp=event.timestamp,
            # run_id is not available — FailureEvent has no run_id field
            # yet (see models/incident_report.py's own docstring on this).
            executive_summary=summary.executive_summary,
            error_category=category,
            severity=severity,
            root_cause_analysis=root_cause.root_cause_analysis,
            confidence_score=root_cause.confidence_score,
            technical_explanation=root_cause.technical_explanation,
            business_impact=root_cause.business_impact,
            step_by_step_resolution=fix.step_by_step_resolution,
            alternative_solutions=fix.alternative_solutions,
            preventive_measures=fix.preventive_measures,
            retry_recommended=fix.retry_recommended,
            retry_notes=fix.retry_notes,
            best_practices=fix.best_practices,
            developer_notes=summary.developer_notes,
        )

    except (
        ClassificationError,
        RootCauseError,
        SummaryError,
        FixRecommendationError,
        ValidationError,
    ) as exc:
        logger.error(
            "Failed to process failure event for flow '%s': %s",
            event.flow_name,
            exc,
        )
        return ProcessingFailure(event=event, error=exc)

    # Log first (durable record), notify second (best-effort).
    incident_id = log_incident(report, db_path=config.INCIDENT_DB_PATH)
    notification_results = send_notification(
        report, [NotificationChannel.TEAMS, NotificationChannel.EMAIL]
    )
    mark_processed(incident_id, db_path=config.INCIDENT_DB_PATH)

    logger.info(
        "Processed '%s' -> incident_id=%s, category=%s, severity=%s",
        event.flow_name,
        incident_id,
        category.value,
        severity.value,
    )

    return ProcessingOutcome(
        incident_id=incident_id,
        report=report,
        notification_results=notification_results,
    )


def process_all_current_failures() -> List[Union[ProcessingOutcome, ProcessingFailure]]:
    """
    Mock-mode batch driver: fetches every currently-active flow and
    currently-failed exception, joins/dedupes them into FailureEvents,
    and processes each one independently.

    This is a stand-in for the real trigger model described in the
    master prompt (a Dataverse workflow firing per new Exception
    record, or a lightweight external scheduler invoking the Agent).
    Today, with no live Dataverse connection, "process everything
    currently failed" is the only mode available — this function is
    NOT the intended production trigger shape, just how Phase 2 mock
    mode exercises the pipeline.
    """
    client = DataverseClient(mode=config.DATAVERSE_MODE)

    flows = get_active_flows(client).flows
    exceptions = get_failed_exceptions(client).exceptions
    events = filter_and_join(flows, exceptions)

    logger.info(
        "Fetched %d active flows, %d failed exceptions -> %d FailureEvents",
        len(flows),
        len(exceptions),
        len(events),
    )

    results: List[Union[ProcessingOutcome, ProcessingFailure]] = []
    for event in events:
        results.append(process_failure_event(event))

    succeeded = sum(1 for r in results if isinstance(r, ProcessingOutcome))
    failed = len(results) - succeeded
    logger.info("Batch complete: %d succeeded, %d failed", succeeded, failed)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    outcomes = process_all_current_failures()

    for outcome in outcomes:
        if isinstance(outcome, ProcessingOutcome):
            print(
                f"OK  {outcome.report.flow_name} -> "
                f"{outcome.report.error_category.value} / "
                f"{outcome.report.severity.value} "
                f"(incident_id={outcome.incident_id})"
            )
        else:
            print(f"FAIL  {outcome.event.flow_name} -> {outcome.error}")