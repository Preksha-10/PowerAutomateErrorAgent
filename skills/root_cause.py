"""
skills/root_cause.py

Extracts and validates the root-cause portion (root_cause_analysis,
confidence_score, technical_explanation, business_impact) of a failure's
LLM analysis.

Same batching design as skills/classifier.py: this function takes an
already-fetched LLM response dict, shared across all four reasoning
skills for one failure event, rather than fetching its own copy. See
classifier.py's module docstring for the full reasoning — the short
version is that four independent fetches would become four real API
calls the moment a live LLM endpoint replaces the stub, silently
breaking the master prompt's one-call-per-event cost rule.
"""

from dataclasses import dataclass


class RootCauseError(Exception):
    """
    Raised when the LLM response is missing a required root-cause field,
    has a confidence_score outside 0.0-1.0, or has a blank text field.

    Deliberately specific, mirroring ClassificationError in
    classifier.py, so a caller knows exactly which reasoning stage
    produced bad output.
    """


@dataclass
class RootCauseAnalysis:
    """
    Validated root-cause portion of an LLM response.

    A dataclass rather than a plain tuple: four unnamed positional
    values stop being self-documenting fast (result[2] tells a reader
    nothing), whereas result.technical_explanation does. Matches the
    @dataclass convention already established by models/failure_event.py.
    """

    root_cause_analysis: str
    confidence_score: float
    technical_explanation: str
    business_impact: str


def _require_nonblank_text(llm_response: dict, field_name: str) -> str:
    """
    Pulls a text field and rejects missing/blank values. An LLM response
    that technically has the key but returns an empty string is still a
    broken response — it would silently produce an IncidentReport with a
    blank root cause, which defeats the point of the whole project.
    """
    value = llm_response.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RootCauseError(
            f"LLM response is missing or has a blank '{field_name}' — "
            f"got {value!r}. This field must be a non-empty string."
        )
    return value


def extract_root_cause(llm_response: dict) -> RootCauseAnalysis:
    """
    Extracts and validates a RootCauseAnalysis from a shared LLM
    response dict.

    Args:
        llm_response: the dict returned by utils.llm_stub.get_stub_response()
            (or, later, parsed JSON from a real LLM call), shared across
            all four reasoning skills for a single failure event.

    Returns:
        A validated RootCauseAnalysis.

    Raises:
        RootCauseError: if any required field is missing, blank, or
            (for confidence_score) outside the valid 0.0-1.0 range.
    """
    root_cause_analysis = _require_nonblank_text(llm_response, "root_cause_analysis")
    technical_explanation = _require_nonblank_text(llm_response, "technical_explanation")
    business_impact = _require_nonblank_text(llm_response, "business_impact")

    raw_confidence = llm_response.get("confidence_score")
    if not isinstance(raw_confidence, (int, float)) or isinstance(raw_confidence, bool):
        raise RootCauseError(
            f"LLM response's confidence_score must be a number, got "
            f"{raw_confidence!r} ({type(raw_confidence).__name__})."
        )
    confidence_score = float(raw_confidence)
    if not (0.0 <= confidence_score <= 1.0):
        raise RootCauseError(
            f"LLM response's confidence_score must be between 0.0 and "
            f"1.0, got {confidence_score}."
        )

    return RootCauseAnalysis(
        root_cause_analysis=root_cause_analysis,
        confidence_score=confidence_score,
        technical_explanation=technical_explanation,
        business_impact=business_impact,
    )