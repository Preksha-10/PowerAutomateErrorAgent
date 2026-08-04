# Summary and Fix Prompt Section

## Rationale (not sent to the LLM — for humans reading this repo)

This section covers everything actionable: the executive summary,
concrete resolution steps, alternatives, prevention, retry guidance,
and best practices. This is deliberately the LAST section concatenated
into the batched prompt, so the model has already reasoned through
classification and root cause before being asked to recommend fixes —
fixes grounded in an already-established root cause are more reliable
than fixes generated in isolation.

This file also documents the final assembly and output-format
instruction, since it's the last section — the JSON schema
instruction has to come after all three sections' field requests are
known to the model.

<!-- TEMPLATE START -->
## Step 3: Summary and Fix Recommendations

Produce:
- executive_summary: 1-2 sentences, written for a non-technical reader,
  summarizing what broke and the likely fix
- step_by_step_resolution: ordered list of concrete, specific actions
  (not "check the logs" — say what to check and what to look for)
- alternative_solutions: list of other valid approaches if the primary
  resolution doesn't apply or isn't preferred
- preventive_measures: list of changes that would stop this recurring
- retry_recommended: true/false — would simply re-running this flow
  likely succeed, given the root cause? (e.g. true for a transient
  timeout, false for a permission error that will fail identically)
- retry_notes: one short qualifier on the retry recommendation, or null
- best_practices: list of general good-practice notes relevant to this
  failure type
- developer_notes: any technical detail worth flagging to a developer
  that doesn't fit the fields above (or empty string if none)

## Output Format

Respond with ONLY a single JSON object, no preamble, no markdown code
fences, no explanation outside the JSON. The object must contain
exactly these keys, matching the fields defined across all three
sections above:

error_category, severity, root_cause_analysis, confidence_score,
technical_explanation, business_impact, executive_summary,
step_by_step_resolution, alternative_solutions, preventive_measures,
retry_recommended, retry_notes, best_practices, developer_notes

Do NOT include related_documentation or similar_historical_errors —
those are populated separately by the Knowledge Base and Microsoft
Learn Search tools, not by this reasoning step.

Do NOT include flow_name, environment, machine_name, timestamp, or
run_id — those are already known from the input event and will be
filled in programmatically, not by you.
<!-- TEMPLATE END -->