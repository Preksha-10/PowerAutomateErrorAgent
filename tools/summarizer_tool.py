"""
tools/summarizer_tool.py

Foundry Agent Function Tool wrapping skills/summarizer.py's
extract_summary().

Same architecture note as tools/classifier_tool.py.
"""

from typing import Any, Dict, Optional

from skills.summarizer import SummaryError, extract_summary

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "summarizer_tool",
        "description": (
            "Validates and records a plain-language executive summary "
            "for a failure, plus optional developer notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "executive_summary": {
                    "type": "string",
                    "description": (
                        "1-2 sentences, written for a non-technical "
                        "reader, summarizing what broke and the likely "
                        "fix. Must be non-empty."
                    ),
                },
                "developer_notes": {
                    "type": "string",
                    "description": (
                        "Optional technical detail worth flagging to a "
                        "developer that doesn't fit elsewhere. Empty "
                        "string is fine if there's nothing extra to add."
                    ),
                },
            },
            "required": ["executive_summary"],
        },
    },
}


def summarizer_tool(
    executive_summary: str, developer_notes: Optional[str] = ""
) -> Dict[str, Any]:
    """
    Validates the Agent's own summary.

    Returns:
        On success: {"success": True, "executive_summary": ..., "developer_notes": ...}
        On failure: {"success": False, "error": "<message>"} — e.g. a
            blank executive_summary. Feed this back to the Agent so it
            can retry with a corrected value.
    """
    try:
        result = extract_summary(
            {
                "executive_summary": executive_summary,
                "developer_notes": developer_notes or "",
            }
        )
    except SummaryError as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "executive_summary": result.executive_summary,
        "developer_notes": result.developer_notes,
    }