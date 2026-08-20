"""
tests/test_microsoft_learn_mcp_tool.py

Tests for tools/microsoft_learn_mcp_tool.py.
This is a structural/configuration test, not a live network test —
build_microsoft_learn_mcp_tool() constructs an SDK object describing
how to connect to the MCP server; it never actually calls
learn.microsoft.com. Verifies the configuration values are exactly
what was verified against the installed SDK and official docs.
"""

from azure.ai.projects.models import MCPTool

from tools.microsoft_learn_mcp_tool import (
    MICROSOFT_LEARN_ALLOWED_TOOLS,
    MICROSOFT_LEARN_MCP_SERVER_LABEL,
    MICROSOFT_LEARN_MCP_SERVER_URL,
    build_microsoft_learn_mcp_tool,
)


def test_builds_a_real_mcp_tool_instance():
    """Confirms the factory returns an actual MCPTool object, not a
    plain dict or something that merely looks right."""
    tool = build_microsoft_learn_mcp_tool()

    assert isinstance(tool, MCPTool)
    assert tool.type == "mcp"


def test_server_label_and_url_are_correct():
    """The label/URL must match the verified official Microsoft Learn
    MCP endpoint exactly — a typo here means the Agent silently can't
    reach the right server."""
    tool = build_microsoft_learn_mcp_tool()

    assert tool.server_label == MICROSOFT_LEARN_MCP_SERVER_LABEL
    assert tool.server_url == MICROSOFT_LEARN_MCP_SERVER_URL
    assert tool.server_url == "https://learn.microsoft.com/api/mcp"


def test_require_approval_is_never_not_always():
    """
    This is the critical unattended-operation guard: if this were
    "always" (the SDK's own default), a real run would stall waiting
    for a human approval that never comes. This test protects against
    that regression specifically — it's the single most important
    assertion in this file.
    """
    tool = build_microsoft_learn_mcp_tool()

    assert tool.require_approval == "never"


def test_allowed_tools_is_an_explicit_allow_list_not_unrestricted():
    """
    allowed_tools must be set to a specific list, not left unset
    (which would grant the whole server's tool surface unrestricted
    access) — matches the least-privilege pattern used elsewhere in
    this project.
    """
    tool = build_microsoft_learn_mcp_tool()

    assert tool.allowed_tools == MICROSOFT_LEARN_ALLOWED_TOOLS
    assert "microsoft_docs_search" in tool.allowed_tools
    assert "microsoft_docs_fetch" in tool.allowed_tools
    assert "microsoft_code_sample_search" in tool.allowed_tools
    assert len(tool.allowed_tools) == 3


def test_each_call_returns_a_fresh_instance():
    """
    build_microsoft_learn_mcp_tool() is a factory, not a cached
    singleton — each call should return its own object, so nothing
    downstream can accidentally share/mutate one Agent's tool
    configuration into another's.
    """
    tool_a = build_microsoft_learn_mcp_tool()
    tool_b = build_microsoft_learn_mcp_tool()

    assert tool_a is not tool_b