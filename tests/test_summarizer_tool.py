"""
tests/test_summarizer_tool.py

Tests for tools/summarizer_tool.py.
"""

from tools.summarizer_tool import summarizer_tool


def test_valid_inputs_return_success_true():
    result = summarizer_tool(
        executive_summary="The flow failed due to a locked file.",
        developer_notes="First occurrence.",
    )

    assert result["success"] is True
    assert result["executive_summary"] == "The flow failed due to a locked file."


def test_empty_developer_notes_is_accepted():
    result = summarizer_tool(executive_summary="Valid summary.", developer_notes="")

    assert result["success"] is True
    assert result["developer_notes"] == ""


def test_missing_developer_notes_defaults_to_empty_string():
    result = summarizer_tool(executive_summary="Valid summary.")

    assert result["success"] is True
    assert result["developer_notes"] == ""


def test_blank_executive_summary_returns_success_false_not_raises():
    result = summarizer_tool(executive_summary="   ")

    assert result["success"] is False
    assert "executive_summary" in result["error"]