"""
skills/summarizer.py

Extracts and validates the narrative-summary portion (executive_summary,
developer_notes) of a failure's LLM analysis.

Same batching design as skills/classifier.py and skills/root_cause.py:
this function takes an already-fetched LLM response dict, shared across
all four reasoning skills for one failure event, rather than fetching
its own copy. See classifier.py's module docstring for the full
reasoning on why that matters for the master prompt's one-call-per-event
cost rule.
"""

from dataclasses import dataclass
from typing import Optional


class SummaryError(Exception):
    """
    Raised when the LLM response is missing or has a blank
    executive_summary, or when developer_notes is present but not a
    string.

    Deliberately specific, mirroring ClassificationError and
    RootCauseError, so a caller knows exactly which reasoning stage
    produced bad output.
    """


@dataclass
class Summary:
    """
    Validated narrative-summary portion of an LLM response.

    developer_notes defaults to "" (matching IncidentReport's own
    default) rather than being required non-blank like
    executive_summary — an LLM legitimately has nothing extra to flag
    most of the time, and treating that as an error would reject
    perfectly valid responses.
    """

    executive_summary: str
    developer_notes: str = ""


def extract_summary(llm_response: dict) -> Summary:
    """
    Extracts and validates a Summary from a shared LLM response dict.

    Args:
        llm_response: the dict returned by utils.llm_stub.get_stub_response()
            (or, later, parsed JSON from a real LLM call), shared across
            all four reasoning skills for a single failure event.

    Returns:
        A validated Summary.

    Raises:
        SummaryError: if executive_summary is missing/blank, or if
            developer_notes is present but not a string.
    """
    raw_summary = llm_response.get("executive_summary")
    if not isinstance(raw_summary, str) or not raw_summary.strip():
        raise SummaryError(
            f"LLM response is missing or has a blank 'executive_summary' "
            f"— got {raw_summary!r}. This field must be a non-empty string; "
            f"it's the first thing a non-technical reader sees."
        )

    raw_notes: Optional[str] = llm_response.get("developer_notes", "")
    if raw_notes is None:
        raw_notes = ""
    if not isinstance(raw_notes, str):
        raise SummaryError(
            f"LLM response's developer_notes must be a string (an empty "
            f"one is fine), got {raw_notes!r} ({type(raw_notes).__name__})."
        )

    return Summary(
        executive_summary=raw_summary,
        developer_notes=raw_notes,
    )