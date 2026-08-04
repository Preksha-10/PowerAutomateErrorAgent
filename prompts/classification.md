# Classification Prompt Section

## Rationale (not sent to the LLM — for humans reading this repo)

This section instructs the model on error_category and severity —
the two fields that categorize *what kind* of failure this is,
before any explanation of *why* it happened. Kept separate from
root_cause.md so a developer tuning the category taxonomy doesn't
need to touch root-cause wording, even though at runtime this whole
file gets concatenated with the other two into a single prompt.

<!-- TEMPLATE START -->
## Step 1: Classification

Given the failure event data below, classify it using EXACTLY one value
from each of these fixed vocabularies. Do not invent new category or
severity values — pick the closest match.

**error_category** must be one of:
Cloud Flow Failure, PAD Runtime Failure, UI Element Not Found,
Invalid/Dynamic Selector, Browser Timeout, Excel Locked/Missing,
SAP Window Missing, OCR Failure, File Not Found, Permission Denied,
Authentication Failed, HTTP/API Error, Timeout, Connector Failure,
SQL Error, Machine Offline, Environment Issue, Unexpected Exception

**severity** must be one of: Low, Medium, High, Critical
- Critical: production flow down, no workaround, business-blocking
- High: production flow failing repeatedly, workaround exists but costly
- Medium: intermittent failure or non-production environment
- Low: cosmetic, single occurrence, self-resolving

Base the classification on the exception_type and error_message fields,
not just the flow name.
<!-- TEMPLATE END -->