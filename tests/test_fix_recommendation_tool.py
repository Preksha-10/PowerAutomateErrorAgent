"""
tests/test_fix_recommendation_tool.py

Tests for tools/fix_recommendation_tool.py.
"""

from tools.fix_recommendation_tool import fix_recommendation_tool


def test_valid_inputs_return_success_true():
    result = fix_recommendation_tool(
        step_by_step_resolution=["Check the file lock.", "Retry the run."],
        retry_recommended=True,
    )

    assert result["success"] is True
    assert result["step_by_step_resolution"] == ["Check the file lock.", "Retry the run."]
    assert result["alternative_solutions"] == []


def test_empty_resolution_steps_returns_success_false_not_raises():
    result = fix_recommendation_tool(
        step_by_step_resolution=[], retry_recommended=False
    )

    assert result["success"] is False
    assert "step_by_step_resolution" in result["error"]


def test_non_bool_retry_recommended_returns_success_false_not_raises():
    result = fix_recommendation_tool(
        step_by_step_resolution=["Do something."], retry_recommended="true"
    )

    assert result["success"] is False
    assert "retry_recommended" in result["error"]


def test_optional_lists_default_correctly_when_omitted():
    result = fix_recommendation_tool(
        step_by_step_resolution=["Do something."], retry_recommended=True
    )

    assert result["success"] is True
    assert result["alternative_solutions"] == []
    assert result["preventive_measures"] == []
    assert result["best_practices"] == []
    assert result["retry_notes"] is None