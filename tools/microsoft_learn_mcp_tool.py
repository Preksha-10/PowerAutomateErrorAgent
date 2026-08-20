"""
tools/microsoft_learn_mcp_tool.py

Registers the Microsoft Learn MCP server as a bound tool on the
autonomous Foundry Agent, giving it access to current, official
Microsoft documentation while reasoning about a failure — rather than
relying solely on the model's own (possibly stale) training knowledge.

VERIFIED directly against the installed azure-ai-projects SDK (not
secondhand docs): MCPTool lives in azure.ai.projects.models (NOT
azure.ai.agents.models, and NOT "McpTool" — it's "MCPTool", all-caps
MCP). Confirmed by constructing a real instance and inspecting its
fields:

    server_label:     str, required
    server_url:        str (one of server_url or connector_id required)
    require_approval:   Literal["always"], Literal["never"] — "always"
                          means a human must approve every tool call,
                          which would stall an unattended run forever
    allowed_tools:       list[str] — explicit allow-list of which tools
                          on the server this Agent may call

Endpoint verified against official Microsoft documentation (2026):
https://learn.microsoft.com/api/mcp, unauthenticated.

DESIGN DECISION — require_approval="never": every tool this server
exposes (microsoft_docs_search, microsoft_docs_fetch,
microsoft_code_sample_search) is read-only — searching/fetching public
documentation, nothing that writes or changes anything. Microsoft's own
guidance distinguishes read-only tools (safe to auto-approve) from
action-taking tools like CreateTicket/RestartFlow (should stay
"always"). PowerAutomateErrorAgent runs UNATTENDED — "always" here
would mean a real run stalls waiting for a human approval that never
comes, so "never" is the correct choice for this specific tool, not a
shortcut taken for convenience.
"""

from azure.ai.projects.models import MCPTool

MICROSOFT_LEARN_MCP_SERVER_LABEL = "microsoft-learn"
MICROSOFT_LEARN_MCP_SERVER_URL = "https://learn.microsoft.com/api/mcp"

# Explicit allow-list, not the whole server unrestricted — matches the
# least-privilege pattern already used elsewhere in this project (e.g.
# scoping the Foundry User Azure role narrowly rather than granting
# broad subscription access).
MICROSOFT_LEARN_ALLOWED_TOOLS = [
    "microsoft_docs_search",
    "microsoft_docs_fetch",
    "microsoft_code_sample_search",
]


def build_microsoft_learn_mcp_tool() -> MCPTool:
    """
    Builds the MCPTool object for binding to the Agent at construction
    time. Factory function, not a module-level constant, so importing
    this module doesn't construct an SDK object as a side effect of
    import — keeps this file cheap to import in contexts that only
    need the label/URL/allowed-tools constants above (e.g. tests that
    check configuration values without needing a live SDK object).

    Returns:
        An MCPTool configured for read-only, unattended Microsoft Learn
        documentation search/fetch, auto-approved (require_approval=
        "never") since every allowed tool is read-only.
    """
    return MCPTool(
        server_label=MICROSOFT_LEARN_MCP_SERVER_LABEL,
        server_url=MICROSOFT_LEARN_MCP_SERVER_URL,
        require_approval="never",
        allowed_tools=MICROSOFT_LEARN_ALLOWED_TOOLS,
    )