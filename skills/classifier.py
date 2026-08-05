"""
skills/classifier.py

Extracts and validates the classification portion (error_category,
severity) of a failure's LLM analysis.

DESIGN NOTE ON BATCHING: this function takes an already-fetched LLM
response dict, not a FailureEvent payload it fetches itself. The master
prompt's cost rule is one batched LLM call per failure event, covering
classification + root cause + fix + summary together. If this skill (and
root_cause.py, summarizer.py, fix_recommendation.py) each called
utils.llm_stub.get_stub_response() independently, that would become four
real API calls the moment the stub is replaced with a live endpoint —
a silent 4x cost/latency regression that no test would catch, since the
stub is free today. Instead, something upstream (the future Agent
orchestrator) fetches the response ONCE and passes the same dict to every
skill. Each skill's job is only to extract and validate its own slice.
"""

from typing import Tuple

from models.incident_report import ErrorCategory, Severity


class ClassificationError(Exception):
    """
    Raised when the LLM response's error_category or severity value
    doesn't match the fixed vocabulary in models/incident_report.py.

    Deliberately specific (not a bare ValueError) so a caller catching
    this knows exactly which stage of reasoning produced bad output,
    rather than a generic Pydantic ValidationError surfacing much later
    when the full IncidentReport is assembled.
    """


def classify(llm_response: dict) -> Tuple[ErrorCategory, Severity]:
    """
    Extracts and validates (error_category, severity) from a shared LLM
    response dict.

    Args:
        llm_response: the dict returned by utils.llm_stub.get_stub_response()
            (or, later, the parsed JSON from a real LLM call), shared
            across all four reasoning skills for a single failure event.

    Returns:
        A (ErrorCategory, Severity) tuple of validated enum members.

    Raises:
        ClassificationError: if either field is missing or doesn't match
            a known enum value.
    """
    raw_category = llm_response.get("error_category")
    try:
        category = ErrorCategory(raw_category)
    except ValueError as exc:
        raise ClassificationError(
            f"LLM response returned an unrecognized error_category: "
            f"{raw_category!r}. Expected one of: "
            f"{[c.value for c in ErrorCategory]}"
        ) from exc

    raw_severity = llm_response.get("severity")
    try:
        severity = Severity(raw_severity)
    except ValueError as exc:
        raise ClassificationError(
            f"LLM response returned an unrecognized severity: "
            f"{raw_severity!r}. Expected one of: "
            f"{[s.value for s in Severity]}"
        ) from exc

    return category, severity