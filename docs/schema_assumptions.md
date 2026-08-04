# Dataverse Schema Assumptions (Phase 0)

**Status: UNVALIDATED.** Everything in this document is an assumption carried
over from the master prompt. Nothing here has been checked against a real
Dataverse environment. Before any tool in `tools/dataverse_*_tool.py` is
pointed at a live Web API, every logical name below must be re-verified via
the `EntityDefinitions` metadata endpoint:

GET [Dataverse URL]/api/data/v9.2/EntityDefinitions(LogicalName='<entity>')
    ?$expand=Attributes($select=LogicalName,AttributeType)

Why this matters: real Dataverse logical names are rarely the "friendly"
names a schema doc uses. A custom table called "Flows" might really be
cr3a2_flow or new_flow, a lookup column is stored as _fieldname_value,
and choice/status fields are integers (statuscode, statecode), not the
strings shown below. Hardcoding any of these before validation is the #1 way
this project breaks silently in Phase 2.

## 1. Flows table (assumed logical name: cr_flows or the built-in
   Power Automate flow entity — must confirm which one we're actually
   using)

| Assumed column      | Assumed type          | Notes |
|----------------------|------------------------|-------|
| Flow ID               | GUID (primary key)     | likely cr_flowid or workflowid if using the built-in entity |
| Flow Name             | Text                   | likely cr_flowname or name |
| Environment            | Text or Choice          | not standard on the built-in flow entity — probably a custom column if we use cr_flows |
| Owner                  | Lookup (systemuser)     | ownerid on most Dataverse tables by default |
| Status (Enabled/Disabled) | Choice/boolean        | on the built-in entity this is statecode/statuscode, not a text field |
| Flow Type (Cloud/Desktop) | Choice                 | custom column, no standard equivalent |

## 2. Exceptions/Errors table (assumed logical name: cr_flowexceptions,
   fully custom — no Dataverse built-in equivalent)

| Assumed column        | Assumed type            | Notes |
|-------------------------|---------------------------|-------|
| Exception ID              | GUID (primary key)         | likely cr_flowexceptionid |
| Related Flow ID            | Lookup → Flows table         | stored as _cr_flowid_value in Web API responses; $expand=cr_flowid(...) to pull related flow fields |
| Run ID                     | Text                        | flow run identifier, for constructing "link to failed run" |
| Error Message                | Text (multiline)             | cr_errormessage |
| Exception Type                | Text                        | cr_exceptiontype |
| Action Name                    | Text                        | which step failed |
| Timestamp                      | DateTime                    | likely just createdon rather than a custom column |
| Status (Failed/Resolved/Retried) | Choice                     | almost certainly an integer statuscode, e.g. 100000001 for Failed — the exact integer mapping MUST be pulled from metadata, never guessed |
| Machine Name (PAD)               | Text                        | custom column, cr_machinename |
| Severity (if pre-tagged)          | Choice                       | optional, may not exist yet |

## 3. Open questions to resolve once we have Dataverse access

1. Is the Flows table a fully custom entity (cr_flows) or are we reusing
   the built-in Power Automate workflow entity? These have very different
   schemas and this changes every query in dataverse_flows_tool.py.
2. What are the real integer values behind the Exceptions statuscode
   choice field (Failed / Resolved / Retried)? Never hardcode a guessed
   integer — pull it from GlobalOptionSetDefinitions or the attribute
   metadata.
3. Does the Exceptions table already exist, or does it need to be created?
   If it needs to be created, the column logical names are ours to choose —
   worth deciding the final names now so the mock JSON in sample_errors/
   doesn't drift from what actually gets built.
4. Confirm the lookup field's exact Web API name — Dataverse lookups always
   serialize as _<schemaname>_value in JSON, e.g. _cr_flowid_value, which
   trips people up the first time.

## 4. How mock data (Phase 1) relates to this

Person A's sample_errors/mock_flows.json and mock_exceptions.json, and
the FlowRecord/ExceptionRecord models, are built against the assumed
schema above — using the friendly field names, not the real Dataverse
_value / integer-choice quirks, since none of that exists yet to validate
against. Every field in those models carries a comment pointing back to this
file. When real EntityDefinitions access lands, the only files that should
need to change are: services/dataverse_client.py (swap mock transport for
live OData calls) and models/flow_record.py /
models/exception_record.py (rename fields to match verified logical
names). Nothing downstream of FailureEvent should need to change at all —
that's the whole point of the seam.
