"""
skills/fix_recommendation.py

Extracts and validates the actionable-guidance portion
(step_by_step_resolution, alternative_solutions, preventive_measures,
retry_recommended, retry_notes, best_practices) of a failure's LLM
analysis.

Same batching design as the other three reasoning skills: this function
takes an already-fetched LLM response dict, shared across all four
skills for one failure event, rather than fetching its own copy. See
classifier.py's module docstring for the full reasoning on why that
matters for the master prompt's one-call-per-event cost rule.
"""

from dataclasses import dataclass, field
from typing import List, Optional


class FixRecommendationError(Exception):
    """
    Raised when the LLM response is missing required fields, has a
    non-list value where a list is expected, has a blank string inside
    a list, or has a non-bool retry_recommended.

    Deliberately specific, mirroring the other three skills' error
    classes, so a caller knows exactly which reasoning stage produced
    bad output.
    """


@dataclass
class FixRecommendation:
    """
    Validated actionable-guidance portion of an LLM response.

    step_by_step_resolution is the one list field required to be
    non-empty — a report with zero resolution steps gives a developer
    nothing to act on. The other list fields default to [] (matching
    IncidentReport's own defaults) since alternatives, prevention, and
    best practices are genuinely optional extras.
    """

    step_by_step_resolution: List[str]
    retry_recommended: bool
    alternative_solutions: List[str] = field(default_factory=list)
    preventive_measures: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    retry_notes: Optional[str] = None


def _validate_string_list(
    llm_response: dict, field_name: str, require_nonempty: bool
) -> List[str]:
    """
    Pulls a list-of-strings field, checks it's actually a list of
    non-blank strings, and (only for fields where it matters, i.e.
    step_by_step_resolution) requires at least one item.
    """
    value = llm_response.get(field_name, [] if not require_nonempty else None)

    if not isinstance(value, list):
        raise FixRecommendationError(
            f"LLM response's '{field_name}' must be a list, got "
            f"{value!r} ({type(value).__name__})."
        )
    if require_nonempty and len(value) == 0:
        raise FixRecommendationError(
            f"LLM response's '{field_name}' must contain at least one "
            f"step — a report with zero resolution steps gives a "
            f"developer nothing to act on."
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise FixRecommendationError(
                f"LLM response's '{field_name}' contains a blank or "
                f"non-string item: {item!r}."
            )
    return value


def extract_fix_recommendation(llm_response: dict) -> FixRecommendation:
    """
    Extracts and validates a FixRecommendation from a shared LLM
    response dict.

    Args:
        llm_response: the dict returned by utils.llm_stub.get_stub_response()
            (or, later, parsed JSON from a real LLM call), shared across
            all four reasoning skills for a single failure event.

    Returns:
        A validated FixRecommendation.

    Raises:
        FixRecommendationError: if step_by_step_resolution is missing/
            empty/malformed, any list field contains a blank item, or
            retry_recommended is missing or not a real bool.
    """
    step_by_step_resolution = _validate_string_list(
        llm_response, "step_by_step_resolution", require_nonempty=True
    )
    alternative_solutions = _validate_string_list(
        llm_response, "alternative_solutions", require_nonempty=False
    )
    preventive_measures = _validate_string_list(
        llm_response, "preventive_measures", require_nonempty=False
    )
    best_practices = _validate_string_list(
        llm_response, "best_practices", require_nonempty=False
    )

    raw_retry = llm_response.get("retry_recommended")
    if not isinstance(raw_retry, bool):
        raise FixRecommendationError(
            f"LLM response's 'retry_recommended' must be a real boolean, "
            f"got {raw_retry!r} ({type(raw_retry).__name__}). A future "
            f"automated-retry system may act on this field directly, so "
            f"a loosely-typed value here (e.g. the string 'true') is not "
            f"acceptable."
        )

    raw_notes = llm_response.get("retry_notes")
    if raw_notes is not None and not isinstance(raw_notes, str):
        raise FixRecommendationError(
            f"LLM response's 'retry_notes' must be a string or null, "
            f"got {raw_notes!r} ({type(raw_notes).__name__})."
        )

    return FixRecommendation(
        step_by_step_resolution=step_by_step_resolution,
        retry_recommended=raw_retry,
        alternative_solutions=alternative_solutions,
        preventive_measures=preventive_measures,
        best_practices=best_practices,
        retry_notes=raw_notes,
    )