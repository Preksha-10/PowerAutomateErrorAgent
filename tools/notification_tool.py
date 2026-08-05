"""
tools/notification_tool.py

Sends a finished IncidentReport to developers via Teams and/or Email.

Today, "sending" means logging the formatted message — there is no live
Logic Apps (Teams) or Graph API (Email) connection yet. The design
isolates that limitation behind two small transport functions
(_send_via_teams_transport, _send_via_email_transport) so swapping in
real integrations later means replacing those two function bodies only;
send_teams_notification(), send_email_notification(), and every caller
of them stay unchanged.

Per the master prompt: template once, reuse for both channels. Both
channels render through the same _render_notification_message(), so a
wording change only needs to happen in one place.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List

from models.incident_report import IncidentReport

logger = logging.getLogger("power_automate_error_agent.notifications")


class NotificationChannel(str, Enum):
    """The channels a notification can be dispatched to."""

    TEAMS = "Teams"
    EMAIL = "Email"


@dataclass
class NotificationResult:
    """
    Outcome of a single notification dispatch attempt.

    Returned rather than None so a future orchestrator or the Incident
    Logger can check success/failure and decide whether to retry, log
    the outcome, or surface it to a developer.
    """

    channel: NotificationChannel
    success: bool
    sent_at: datetime
    rendered_message: str


def _render_notification_message(report: IncidentReport) -> str:
    """
    Builds the single shared notification template from an
    IncidentReport's notification payload.

    Reuses IncidentReport.to_notification_payload() rather than reaching
    into the full report directly — that method is the enforcement point
    for exactly which fields a notification is allowed to contain (see
    its docstring in models/incident_report.py).
    """
    payload = report.to_notification_payload()

    link_line = (
        f"Run ID: {payload['run_id']}"
        if payload["run_id"]
        else "Run ID: (not available)"
    )

    return (
        f"[{payload['priority']}] Flow Failure: {payload['flow_name']}\n"
        f"Environment: {payload['environment']}\n"
        f"Machine: {payload['machine_name']}\n"
        f"Timestamp: {payload['timestamp']}\n"
        f"{link_line}\n"
        f"\n"
        f"Summary: {payload['error_summary']}\n"
        f"Root Cause: {payload['root_cause']}\n"
        f"Recommended Fix: {payload['recommended_fix']}\n"
    )


def _send_via_teams_transport(message: str) -> bool:
    """
    Stubbed Teams transport. Logs the message instead of calling a Logic
    Apps connector. Replace this function's body with a real Logic Apps
    HTTP call when that connection exists — no caller needs to change.

    Returns True to represent a successful send, matching the return
    contract a real transport call would have (success/failure).
    """
    logger.info("TEAMS NOTIFICATION (stub — not actually sent):\n%s", message)
    return True


def _send_via_email_transport(message: str) -> bool:
    """
    Stubbed Email transport. Logs the message instead of calling the
    Graph API. Replace this function's body with a real Graph API call
    when that connection exists — no caller needs to change.
    """
    logger.info("EMAIL NOTIFICATION (stub — not actually sent):\n%s", message)
    return True


def send_teams_notification(report: IncidentReport) -> NotificationResult:
    """Renders and dispatches a Teams notification for the given report."""
    message = _render_notification_message(report)
    success = _send_via_teams_transport(message)
    return NotificationResult(
        channel=NotificationChannel.TEAMS,
        success=success,
        sent_at=datetime.now(timezone.utc),
        rendered_message=message,
    )


def send_email_notification(report: IncidentReport) -> NotificationResult:
    """Renders and dispatches an Email notification for the given report."""
    message = _render_notification_message(report)
    success = _send_via_email_transport(message)
    return NotificationResult(
        channel=NotificationChannel.EMAIL,
        success=success,
        sent_at=datetime.now(timezone.utc),
        rendered_message=message,
    )


def send_notification(
    report: IncidentReport, channels: List[NotificationChannel]
) -> List[NotificationResult]:
    """
    Dispatches a notification across multiple channels for one report.

    Args:
        report: the finished, validated IncidentReport to notify about.
        channels: which channels to send to, e.g.
            [NotificationChannel.TEAMS, NotificationChannel.EMAIL].

    Returns:
        A NotificationResult per requested channel, in the same order.
    """
    dispatch_map = {
        NotificationChannel.TEAMS: send_teams_notification,
        NotificationChannel.EMAIL: send_email_notification,
    }

    results = []
    for channel in channels:
        if channel not in dispatch_map:
            raise ValueError(f"Unsupported notification channel: {channel!r}")
        results.append(dispatch_map[channel](report))
    return results