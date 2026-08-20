"""
tools/root_cause_tool.py

Foundry Agent Function Tool wrapping skills/root_cause.py's
extract_root_cause().

Same architecture note as tools/classifier_tool.py: the Agent supplies
these four values as its own reasoned tool-call arguments, rather than
this tool extracting them from a pre-fetched shared LLM response.
extract_root_cause()'s validation logic is unchanged.
"""

from typing import Any, Dict

from skills.root_cause import RootCauseError, extract_root_cause

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "root_cause_tool",
        "description": (
            "Validates and records a root cause analysis for a failure. "
            "Call this after reasoning about WHY the failure happened, "
            "not just what category it falls into."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "root_cause_analysis": {
                    "type": "string",
                    "description": "2-4 sentences on the underlying cause. Must be non-empty.",
                },
                "confidence_score": {
                    "type": "number",
                    "description": (
                        "Genuine confidence in this analysis, 0.0-1.0. "
                        "Use lower values when the error is ambiguous or "
                        "multiple plausible causes exist — do not default "
                        "to a high number to seem authoritative."
                    ),
                },
                "technical_explanation": {
                    "type": "string",
                    "description": "The specific technical mechanism. Must be non-empty.",
                },
                "business_impact": {
                    "type": "string",
                    "description": "1-2 sentences on business impact. Must be non-empty.",
                },
            },
            "required": [
                "root_cause_analysis",
                "confidence_score",
                "technical_explanation",
                "business_impact",
            ],
        },
    },
}


def root_cause_tool(
    root_cause_analysis: str,
    confidence_score: float,
    technical_explanation: str,
    business_impact: str,
) -> Dict[str, Any]:
    """
    Validates the Agent's own root-cause reasoning.

    Returns:
        On success: {"success": True, ...all four validated fields...}
        On failure: {"success": False, "error": "<message>"} — e.g. a
            blank field, or confidence_score outside 0.0-1.0. Feed this
            back to the Agent so it can retry with corrected values.
    """
    try:
        result = extract_root_cause(
            {
                "root_cause_analysis": root_cause_analysis,
                "confidence_score": confidence_score,
                "technical_explanation": technical_explanation,
                "business_impact": business_impact,
            }
        )
    except RootCauseError as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "root_cause_analysis": result.root_cause_analysis,
        "confidence_score": result.confidence_score,
        "technical_explanation": result.technical_explanation,
        "business_impact": result.business_impact,
    }