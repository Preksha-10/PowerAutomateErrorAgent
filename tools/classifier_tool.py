"""
tools/classifier_tool.py

Foundry Agent Function Tool wrapping skills/classifier.py's classify().

ARCHITECTURE NOTE: this project deliberately deviates from the master
prompt's one-batched-LLM-call cost rule (see docs/architecture_decisions.md).
In the old deterministic pipeline, classify() received a pre-fetched
shared LLM response dict. Here, there is no shared response — the
autonomous Agent reasons its way to a category and severity, then calls
this tool WITH those values as explicit arguments. classify()'s own
validation logic is unchanged; only how it's fed changes.

VALIDATION ERRORS ARE RETURNED, NOT RAISED: a ClassificationError here
becomes part of the Agent's own conversation context (a failed tool
call result), giving the model a chance to self-correct on its next
turn, rather than crashing the whole run. This is a genuine advantage
of the agentic architecture worth actually using, not just tolerating
the cost of.
"""

from typing import Any, Dict

from skills.classifier import ClassificationError, classify

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "classifier_tool",
        "description": (
            "Validates a failure's error category and severity against "
            "the project's fixed vocabulary. Call this after reasoning "
            "about what kind of failure occurred and how severe it is."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "error_category": {
                    "type": "string",
                    "description": (
                        "Must be exactly one of: Cloud Flow Failure, PAD "
                        "Runtime Failure, UI Element Not Found, "
                        "Invalid/Dynamic Selector, Browser Timeout, "
                        "Excel Locked/Missing, SAP Window Missing, OCR "
                        "Failure, File Not Found, Permission Denied, "
                        "Authentication Failed, HTTP/API Error, Timeout, "
                        "Connector Failure, SQL Error, Machine Offline, "
                        "Environment Issue, Unexpected Exception."
                    ),
                },
                "severity": {
                    "type": "string",
                    "description": "Must be exactly one of: Low, Medium, High, Critical.",
                },
            },
            "required": ["error_category", "severity"],
        },
    },
}


def classifier_tool(error_category: str, severity: str) -> Dict[str, Any]:
    """
    Validates the Agent's own classification against the fixed
    ErrorCategory/Severity vocabulary.

    Returns:
        On success: {"success": True, "error_category": ..., "severity": ...}
            with the validated, canonical enum string values.
        On failure: {"success": False, "error": "<message>"} — feed this
            back to the Agent as the tool's result so it can retry with
            a corrected value, rather than raising and killing the run.
    """
    try:
        category, sev = classify(
            {"error_category": error_category, "severity": severity}
        )
    except ClassificationError as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "error_category": category.value,
        "severity": sev.value,
    }