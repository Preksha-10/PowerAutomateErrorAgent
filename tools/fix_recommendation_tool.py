"""
tools/fix_recommendation_tool.py

Foundry Agent Function Tool wrapping skills/fix_recommendation.py's
extract_fix_recommendation().

Same architecture note as tools/classifier_tool.py.
"""

from typing import Any, Dict, List, Optional

from skills.fix_recommendation import (
    FixRecommendationError,
    extract_fix_recommendation,
)

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fix_recommendation_tool",
        "description": (
            "Validates and records actionable guidance for a failure: "
            "resolution steps, alternatives, prevention, retry guidance, "
            "and best practices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "step_by_step_resolution": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Ordered list of concrete, specific actions. "
                        "Must contain at least one non-blank step — a "
                        "report with zero resolution steps gives a "
                        "developer nothing to act on."
                    ),
                },
                "alternative_solutions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of alternative approaches. May be empty.",
                },
                "preventive_measures": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of changes that would prevent recurrence. May be empty.",
                },
                "retry_recommended": {
                    "type": "boolean",
                    "description": (
                        "Would simply re-running this flow likely "
                        "succeed, given the root cause? true for a "
                        "transient issue, false for something that will "
                        "fail identically (e.g. a permission error)."
                    ),
                },
                "retry_notes": {
                    "type": "string",
                    "description": "Optional short qualifier on the retry recommendation.",
                },
                "best_practices": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of general good-practice notes. May be empty.",
                },
            },
            "required": ["step_by_step_resolution", "retry_recommended"],
        },
    },
}


def fix_recommendation_tool(
    step_by_step_resolution: List[str],
    retry_recommended: bool,
    alternative_solutions: Optional[List[str]] = None,
    preventive_measures: Optional[List[str]] = None,
    retry_notes: Optional[str] = None,
    best_practices: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Validates the Agent's own fix recommendations.

    Returns:
        On success: {"success": True, ...all six validated fields...}
        On failure: {"success": False, "error": "<message>"} — e.g. an
            empty step_by_step_resolution, a blank item inside a list,
            or retry_recommended not being a real boolean. Feed this
            back to the Agent so it can retry with corrected values.
    """
    try:
        result = extract_fix_recommendation(
            {
                "step_by_step_resolution": step_by_step_resolution,
                "retry_recommended": retry_recommended,
                "alternative_solutions": alternative_solutions or [],
                "preventive_measures": preventive_measures or [],
                "retry_notes": retry_notes,
                "best_practices": best_practices or [],
            }
        )
    except FixRecommendationError as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "step_by_step_resolution": result.step_by_step_resolution,
        "retry_recommended": result.retry_recommended,
        "alternative_solutions": result.alternative_solutions,
        "preventive_measures": result.preventive_measures,
        "retry_notes": result.retry_notes,
        "best_practices": result.best_practices,
    }