"""
utils/llm_stub.py

Mocked stand-in for the real Azure AI Foundry model call.

We have no live model endpoint yet. Every Skill in skills/ that needs
LLM reasoning calls get_stub_response() instead of a real API. This lets
classifier.py, root_cause.py, summarizer.py, and fix_recommendation.py
be built and fully unit-tested today, with only THIS file needing to
change once a real endpoint exists.

Design note: this stub takes the same dict shape FailureEvent.to_llm_payload()
produces, because the real call will eventually receive a prompt string
built from that same dict — matching the contract now means calling code
doesn't change later. It also does simple pattern-matching on the input to
return one of a few realistic canned responses, rather than one fixed blob,
so tests actually exercise "does the caller use the input" rather than
trivially passing regardless of what's fed in.
"""

import json
from typing import Any, Dict


def _match_pattern(payload: Dict[str, Any]) -> str:
    """
    Picks which canned response best fits the input, using the same
    signal fields prompts/classification.md tells the real model to use:
    exception type and error message, not just the flow name.

    Returns a key into _CANNED_RESPONSES. Falls back to "unexpected" for
    anything that doesn't match a known pattern — mirrors how
    ErrorCategory.UNEXPECTED_EXCEPTION is the deliberate fallback in the
    real schema.
    """
    exception = payload.get("exception", "").lower()
    error_message = payload.get("error_message", "").lower()
    action_type = payload.get("action_type", "").lower()

    if "locked" in error_message or "excel" in action_type and "lock" in error_message:
        return "excel_locked"
    if "timeout" in exception or "timeout" in error_message:
        return "timeout"
    if "unauthorized" in error_message or "auth" in exception.lower() or "401" in error_message:
        return "auth_failed"
    if "element not found" in error_message or "selector" in error_message:
        return "ui_element_not_found"
    return "unexpected"


_CANNED_RESPONSES: Dict[str, Dict[str, Any]] = {
    "excel_locked": {
        "error_category": "Excel Locked/Missing",
        "severity": "High",
        "root_cause_analysis": (
            "The source Excel file was open for writing by another process "
            "(likely a concurrent scheduled job) at the moment this flow "
            "attempted to read it, causing a file-lock exception."
        ),
        "confidence_score": 0.85,
        "technical_explanation": (
            "FileLockedException raised on the 'Get Excel Rows' action; the "
            "underlying OS-level file handle was held exclusively by another "
            "writer."
        ),
        "business_impact": (
            "Downstream approvals or records depending on this file are "
            "delayed until the flow is retried."
        ),
        "executive_summary": (
            "The flow failed because the Excel file it reads was locked by "
            "another process; retrying after the lock clears should resolve it."
        ),
        "step_by_step_resolution": [
            "Confirm no other process (scheduled job, open desktop session) "
            "currently has the file open.",
            "Close any open handles on the file.",
            "Retry the flow run.",
        ],
        "alternative_solutions": [
            "Move the data source to SharePoint/Dataverse to avoid file "
            "locking entirely.",
        ],
        "preventive_measures": [
            "Stagger scheduled jobs that read/write this file so they don't "
            "overlap.",
        ],
        "retry_recommended": True,
        "retry_notes": "Safe to retry once the lock is confirmed released.",
        "best_practices": [
            "Avoid multiple automated processes writing to the same Excel "
            "file concurrently.",
        ],
        "developer_notes": "",
    },
    "timeout": {
        "error_category": "Browser Timeout",
        "severity": "Medium",
        "root_cause_analysis": (
            "The target page or element took longer to respond than the "
            "configured wait threshold, most likely due to transient network "
            "or server load rather than a structural change to the page."
        ),
        "confidence_score": 0.6,
        "technical_explanation": (
            "A timeout exception was raised waiting on a UI action; no "
            "further detail on which specific element without a screenshot."
        ),
        "business_impact": (
            "Single run delayed; if this recurs across multiple runs it "
            "indicates a systemic slowdown worth investigating."
        ),
        "executive_summary": (
            "The flow timed out waiting on a step to complete, likely a "
            "one-off slowdown; retrying is reasonable."
        ),
        "step_by_step_resolution": [
            "Check target system/page responsiveness at the time of failure.",
            "Increase the timeout threshold if this recurs frequently.",
            "Retry the flow run.",
        ],
        "alternative_solutions": [
            "Add an explicit wait-for-element step instead of a fixed timeout.",
        ],
        "preventive_measures": [
            "Monitor for repeated timeouts on this action to catch a "
            "systemic issue early.",
        ],
        "retry_recommended": True,
        "retry_notes": "Likely transient; retry is low-risk.",
        "best_practices": [
            "Prefer dynamic wait conditions over fixed timeouts in UI "
            "automation steps.",
        ],
        "developer_notes": "Confidence is moderate — timeouts can mask "
        "several different underlying causes.",
    },
    "auth_failed": {
        "error_category": "Authentication Failed",
        "severity": "Critical",
        "root_cause_analysis": (
            "The connection's credentials or token have expired or been "
            "revoked, causing the connector to reject the request outright."
        ),
        "confidence_score": 0.9,
        "technical_explanation": (
            "A 401 Unauthorized response was returned by the target API; "
            "this is not a transient condition and will fail identically "
            "on retry without credential intervention."
        ),
        "business_impact": (
            "Every run of this flow will fail until credentials are fixed — "
            "this is blocking, not intermittent."
        ),
        "executive_summary": (
            "The flow's connection credentials have expired or are invalid; "
            "it will keep failing until they're refreshed."
        ),
        "step_by_step_resolution": [
            "Open the flow's connection reference and reauthenticate.",
            "Confirm the account used still has the required permissions.",
            "Re-run the flow after reauthentication.",
        ],
        "alternative_solutions": [
            "Switch to a service account with a non-expiring credential "
            "type if this recurs frequently.",
        ],
        "preventive_measures": [
            "Set up expiry alerts for the credential type in use.",
        ],
        "retry_recommended": False,
        "retry_notes": "Retrying without fixing credentials will fail "
        "identically — do not retry until reauthenticated.",
        "best_practices": [
            "Use service accounts with long-lived credentials for "
            "unattended flows.",
        ],
        "developer_notes": "",
    },
    "ui_element_not_found": {
        "error_category": "UI Element Not Found",
        "severity": "High",
        "root_cause_analysis": (
            "The UI selector this step relies on no longer matches an "
            "element on the target page, most likely due to a layout or "
            "version change in the target application."
        ),
        "confidence_score": 0.7,
        "technical_explanation": (
            "The automation engine could not locate the configured selector "
            "within the timeout window; this typically indicates the "
            "selector is stale rather than a transient failure."
        ),
        "business_impact": (
            "This flow will continue failing on every run until the "
            "selector is updated to match the current UI."
        ),
        "executive_summary": (
            "The flow can no longer find a UI element it depends on, likely "
            "because the target application's layout changed; the selector "
            "needs updating."
        ),
        "step_by_step_resolution": [
            "Open the target application and confirm whether the UI has "
            "changed near the failing step.",
            "Update the selector to match the current element.",
            "Re-run the flow to confirm the fix.",
        ],
        "alternative_solutions": [
            "Use a more resilient selector strategy (e.g. accessible name "
            "instead of exact position) to reduce future breakage.",
        ],
        "preventive_measures": [
            "Re-validate UI selectors after any known update to the target "
            "application.",
        ],
        "retry_recommended": False,
        "retry_notes": "Will fail identically until the selector is fixed.",
        "best_practices": [
            "Prefer stable, semantic selectors over brittle positional ones.",
        ],
        "developer_notes": "",
    },
    "unexpected": {
        "error_category": "Unexpected Exception",
        "severity": "Medium",
        "root_cause_analysis": (
            "The error does not match a known failure pattern; manual "
            "review of the full error message and action context is "
            "recommended before drawing conclusions."
        ),
        "confidence_score": 0.3,
        "technical_explanation": (
            "No specific technical mechanism could be inferred from the "
            "available fields."
        ),
        "business_impact": (
            "Impact is unclear without further investigation of this "
            "specific failure."
        ),
        "executive_summary": (
            "This failure doesn't match a known pattern and needs manual "
            "review."
        ),
        "step_by_step_resolution": [
            "Review the full error message and action context manually.",
            "Check recent changes to the flow or target system.",
        ],
        "alternative_solutions": [],
        "preventive_measures": [],
        "retry_recommended": False,
        "retry_notes": "Not recommended without understanding the cause "
        "first.",
        "best_practices": [],
        "developer_notes": "Low-confidence classification — flagged for "
        "manual triage rather than automated handling.",
    },
}


def get_stub_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mocked LLM call. Takes the same dict shape FailureEvent.to_llm_payload()
    produces and returns a dict matching the JSON schema specified in
    prompts/summary_fix.md's "Output Format" section.

    This is what skills/*.py should call today. Swapping in a real Azure
    AI Foundry call later means replacing the body of this function with
    an actual API request — every caller of get_stub_response() stays
    unchanged.
    """
    pattern = _match_pattern(payload)
    # Return a copy so callers mutating the result never corrupt the
    # canned template for the next call.
    return dict(_CANNED_RESPONSES[pattern])


def get_stub_response_as_json_string(payload: Dict[str, Any]) -> str:
    """
    Same as get_stub_response(), but returns a JSON string instead of a
    dict.

    This matters because the real LLM will return raw text, not a
    pre-parsed Python object — prompts/summary_fix.md explicitly instructs
    the model to respond with "ONLY a single JSON object". Skills should
    be tested against THIS function (requiring a json.loads() step), not
    just get_stub_response(), so the parsing step itself gets exercised
    now instead of silently working today and breaking on first contact
    with a real model response.
    """
    return json.dumps(get_stub_response(payload))