"""
tests/test_classifier_tool.py

Tests for tools/classifier_tool.py.
Verifies success and failure return SHAPES specifically — this tool
must never raise, since a raised exception can't become part of an
Agent's tool-call conversation context.
"""

from tools.classifier_tool import classifier_tool


def test_valid_inputs_return_success_true():
    result = classifier_tool(error_category="Timeout", severity="Medium")

    assert result["success"] is True
    assert result["error_category"] == "Timeout"
    assert result["severity"] == "Medium"


def test_invalid_category_returns_success_false_not_raises():
    """This must NOT raise ClassificationError — it must return a dict
    the Agent can see and react to on its next turn."""
    result = classifier_tool(error_category="Nonsense Category", severity="Low")

    assert result["success"] is False
    assert "error" in result
    assert "error_category" in result["error"]


def test_invalid_severity_returns_success_false_not_raises():
    result = classifier_tool(error_category="Timeout", severity="Nonsense")

    assert result["success"] is False
    assert "severity" in result["error"]