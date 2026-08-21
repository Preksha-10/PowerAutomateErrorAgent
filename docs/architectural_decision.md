## ADR-XXX: Autonomous Azure AI Foundry Agent Tool Selection

### Decision

The deterministic one-batched-LLM-call-per-event architecture is being
replaced with an autonomous Azure AI Foundry Agent Service architecture.

The Foundry Agent will have access to the system's tools and will
autonomously determine which tools are required during an investigation.

This intentionally allows multiple LLM/tool-calling turns per failure
event and therefore introduces potentially higher and less predictable
LLM execution cost.

### Rationale

This deviation was accepted for three primary reasons:

1. Accuracy and reduced hallucination

   The agent can retrieve relevant operational evidence through tools
   rather than relying primarily on the LLM's general knowledge. This
   allows analysis to be grounded in the actual failure data available
   from the system.

2. Autonomous tool selection

   The agent can dynamically determine which capabilities are required
   for a particular failure instead of executing a fixed sequence of
   analysis steps for every event.

3. Reduced unnecessary context/tokens

   Rather than passing all potentially relevant data into a single large
   LLM prompt, the agent can retrieve additional information only when
   required. This reduces unnecessary context passed to individual model
   calls.

### Trade-off

The autonomous architecture may require multiple LLM calls and tool
invocations for a single failure event. Consequently, total model
execution cost and latency may be higher and less predictable than the
previous deterministic one-call architecture.

This trade-off is intentional and accepted in favor of better
grounding, autonomous investigation, and more targeted context
retrieval.

### Scope

This decision applies to the migration from the deterministic `app.py`
analysis pipeline to the Azure AI Foundry Agent Service architecture.