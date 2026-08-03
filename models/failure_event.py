"""
models/failure_event.py

Defines the FailureEvent data model — the single, minimal shape
representing a Power Automate (Cloud or Desktop) failure.

This is the ONLY data structure that gets passed to the LLM for
analysis. Keeping it deliberately narrow enforces the cost-optimization
rule: never send full flow definitions, only the essential failure
context.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FailureEvent:
    """
    Represents a single failure captured from a Power Automate
    Cloud Flow or Power Automate Desktop (PAD) run.

    Attributes:
        flow_name: Name of the Cloud Flow or PAD process that failed.
        environment: Which environment the failure occurred in
            (e.g. "Production", "UAT", "Dev").
        action_name: The specific action/step that failed within the flow.
        action_type: The type of action (e.g. "HTTP", "Excel", "SAP",
            "Browser Automation", "OCR").
        exception: The raw exception type/name, if available
            (e.g. "SeleniumTimeoutException").
        error_message: The human-readable error message text.
        timestamp: When the failure occurred.
        machine_name: The machine that ran the flow (relevant for PAD,
            which runs on a specific gateway/desktop machine).
        screenshot_path: Optional path to a screenshot captured at
            failure time (PAD UI automation failures often have one).
    """

    flow_name: str
    environment: str
    action_name: str
    action_type: str
    exception: str
    error_message: str
    timestamp: datetime
    machine_name: str
    screenshot_path: Optional[str] = field(default=None)

    def to_llm_payload(self) -> dict:
        """
        Returns only the fields the LLM actually needs, as a plain dict,
        ready to be inserted into a prompt template.

        This method is the enforcement point for the cost-optimization
        rule: it is the ONLY way FailureEvent data reaches the LLM, and
        it deliberately exposes nothing beyond these fields.
        """
        return {
            "flow_name": self.flow_name,
            "environment": self.environment,
            "action_name": self.action_name,
            "action_type": self.action_type,
            "exception": self.exception,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "machine_name": self.machine_name,
            "has_screenshot": self.screenshot_path is not None,
        }