# Root Cause Prompt Section

## Rationale (not sent to the LLM — for humans reading this repo)

This section produces root_cause_analysis, confidence_score,
technical_explanation, and business_impact. confidence_score exists
because a human reading the incident report needs to know how much to
trust the analysis before acting on it — IncidentReport enforces this
is a 0.0-1.0 float at the schema level, so the prompt just needs to
tell the model to reason honestly about its own certainty, not fake
a high number.

<!-- TEMPLATE START -->
## Step 2: Root Cause Analysis

Explain WHY this failure happened, not just what category it falls
into. Do not simply restate the error message — reason about the
underlying cause (e.g. "Excel Locked/Missing" alone is not a root
cause; "a concurrent scheduled process had the workbook open for
writing" is).

Produce:
- root_cause_analysis: 2-4 sentences on the underlying cause
- confidence_score: your genuine confidence in this analysis, 0.0-1.0.
  Use lower values (below 0.5) when the error message is ambiguous or
  when multiple plausible root causes exist. Do not default to a high
  number to seem authoritative.
- technical_explanation: the specific technical mechanism (exception
  type, failing action, what state the system was in)
- business_impact: 1-2 sentences on what this means for the business
  process this flow supports, inferred from the flow name and
  environment (e.g. Production vs. Dev/Test changes the impact framing)
<!-- TEMPLATE END -->