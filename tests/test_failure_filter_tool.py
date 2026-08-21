import pytest

from tools.failure_filter_tool import (
    TOOL_SCHEMA,
    execute_tool_call,
)


def test_failure_filter_tool_schema():
    assert TOOL_SCHEMA["type"] == "function"

    function_schema = TOOL_SCHEMA["function"]

    assert function_schema["name"] == "filter_failure_events"

    properties = function_schema["parameters"]["properties"]

    assert "flows" in properties
    assert "exceptions" in properties

    assert set(
        function_schema["parameters"]["required"]
    ) == {"flows", "exceptions"}