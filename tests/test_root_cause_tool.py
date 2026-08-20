"""
tests/test_root_cause_tool.py

Tests for tools/root_cause_tool.py.
"""

from tools.root_cause_tool import root_cause_tool


def test_valid_inputs_return_success_true():
    result = root_cause_tool(
        root_cause_analysis="A concurrent process held the file lock.",
        confidence_score=0.8,
        technical_explanation="FileLockedException on read.",
        business_impact="Approvals delayed.",
    )

    assert result["success"] is True
    assert result["confidence_score"] == 0.8


def test_out_of_range_confidence_returns_success_false_not_raises():
    result = root_cause_tool(
        root_cause_analysis="Valid text.",
        confidence_score=1.5,
        technical_explanation="Valid text.",
        business_impact="Valid text.",
    )

    assert result["success"] is False
    assert "confidence_score" in result["error"]


def test_blank_field_returns_success_false_not_raises():
    result = root_cause_tool(
        root_cause_analysis="   ",
        confidence_score=0.5,
        technical_explanation="Valid text.",
        business_impact="Valid text.",
    )

    assert result["success"] is False
    assert "root_cause_analysis" in result["error"]