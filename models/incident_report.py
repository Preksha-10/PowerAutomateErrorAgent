"""
models/incident_report.py

Defines the IncidentReport schema — the finished, validated output of the
AI reasoning pipeline for a single FailureEvent.

This is the ONE place in the project we deliberately use Pydantic instead
of a dataclass. Everywhere else, a dataclass is enough because we control
both ends of the data flow ourselves. Here we don't: this object gets built
from an LLM's response (today, a canned stub; later, a real model call),
then gets parsed into Teams/Email templates and written back to a
Dataverse Incidents table. Strict validation at construction time is what
lets every downstream consumer trust the shape without re-checking it.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Severity(str, Enum):
    """
    Fixed severity vocabulary. An enum (not a free-text string) forces
    normalization at the model boundary — "High", "high", and "HIGH"
    collapse to one value instead of being three different strings that
    a notification-priority router would have to fuzzy-match later.
    """

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ErrorCategory(str, Enum):
    """
    Fixed failure-category vocabulary, taken directly from the master
    prompt's list of categories to classify. UNEXPECTED_EXCEPTION is the
    deliberate fallback for anything that doesn't cleanly match one of
    the known categories, so classification never has to fail outright.
    """

    CLOUD_FLOW_FAILURE = "Cloud Flow Failure"
    PAD_RUNTIME_FAILURE = "PAD Runtime Failure"
    UI_ELEMENT_NOT_FOUND = "UI Element Not Found"
    INVALID_DYNAMIC_SELECTOR = "Invalid/Dynamic Selector"
    BROWSER_TIMEOUT = "Browser Timeout"
    EXCEL_LOCKED_OR_MISSING = "Excel Locked/Missing"
    SAP_WINDOW_MISSING = "SAP Window Missing"
    OCR_FAILURE = "OCR Failure"
    FILE_NOT_FOUND = "File Not Found"
    PERMISSION_DENIED = "Permission Denied"
    AUTHENTICATION_FAILED = "Authentication Failed"
    HTTP_API_ERROR = "HTTP/API Error"
    TIMEOUT = "Timeout"
    CONNECTOR_FAILURE = "Connector Failure"
    SQL_ERROR = "SQL Error"
    MACHINE_OFFLINE = "Machine Offline"
    ENVIRONMENT_ISSUE = "Environment Issue"
    UNEXPECTED_EXCEPTION = "Unexpected Exception"


class DocumentationLink(BaseModel):
    """
    A single related-documentation reference (from the Microsoft Learn
    Search tool). Kept as its own tiny model rather than a raw string so
    the title and URL can't accidentally get swapped or concatenated
    inconsistently across different report-generation runs.
    """

    title: str
    url: HttpUrl


class IncidentReport(BaseModel):
    """
    The complete, validated incident report for one FailureEvent.

    Field groups, matching the master prompt's required output list:
      - Context (which flow/run/machine this report is about)
      - Analysis (summary, category, severity, root cause, confidence)
      - Guidance (resolution steps, alternatives, prevention, best practices)
      - Grounding (docs, historical matches)
      - Metadata (developer notes, generation timestamp)
    """

    # --- Context ---------------------------------------------------------
    flow_name: str
    environment: str
    machine_name: str
    timestamp: datetime = Field(
        description="When the underlying failure occurred (from FailureEvent), "
        "not when this report was generated."
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Flow run identifier, if available, used to construct a "
        "link to the failed run. Not present on FailureEvent today — "
        "populated later once Person A's ingestion layer carries it.",
    )

    # --- Analysis ----------------------------------------------------------
    executive_summary: str
    error_category: ErrorCategory
    severity: Severity
    root_cause_analysis: str
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's confidence in the root cause analysis, 0.0-1.0. "
        "Constrained here so downstream rules (e.g. 'flag for human review "
        "below 0.7') can trust the range without re-validating it.",
    )
    technical_explanation: str
    business_impact: str

    # --- Guidance ------------------------------------------------------------
    step_by_step_resolution: List[str] = Field(default_factory=list)
    alternative_solutions: List[str] = Field(default_factory=list)
    preventive_measures: List[str] = Field(default_factory=list)
    retry_recommended: bool = Field(
        description="Whether an automatic retry is a reasonable next step for "
        "this failure category (e.g. true for a transient timeout, false for "
        "a permission error that will just fail again)."
    )
    retry_notes: Optional[str] = Field(
        default=None,
        description="Short qualifier on the retry recommendation, e.g. "
        "'safe to retry once gateway is back online'.",
    )
    best_practices: List[str] = Field(default_factory=list)

    # --- Grounding -------------------------------------------------------------
    related_documentation: List[DocumentationLink] = Field(default_factory=list)
    similar_historical_errors: List[str] = Field(
        default_factory=list,
        description="Short descriptions of matched past incidents from the "
        "Knowledge Base tool. Empty until that tool exists (future enhancement) "
        "— never required, since a report is still valid with zero matches.",
    )

    # --- Metadata ------------------------------------------------------------
    developer_notes: str = Field(default="")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this IncidentReport was produced, distinct from "
        "`timestamp` (when the flow actually failed).",
    )

    def to_notification_payload(self) -> dict:
        """
        Returns only the fields Teams/Email notifications actually need,
        as a plain dict, ready to drop into the shared notification
        template.

        Mirrors FailureEvent.to_llm_payload() from models/failure_event.py:
        this is the single enforcement point for what a notification is
        allowed to contain. Notification code should never reach into the
        full IncidentReport directly — it should call this method, so
        adding a field to the report doesn't silently leak into a Teams
        message without a deliberate decision to include it here.
        """
        return {
            "flow_name": self.flow_name,
            "machine_name": self.machine_name,
            "timestamp": self.timestamp.isoformat(),
            "environment": self.environment,
            "error_summary": self.executive_summary,
            "root_cause": self.root_cause_analysis,
            "recommended_fix": (
                self.step_by_step_resolution[0]
                if self.step_by_step_resolution
                else "See full incident report."
            ),
            "priority": self.severity.value,
            "run_id": self.run_id,
        }