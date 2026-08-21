"""
tools/incident_logger_tool.py

Writes a finished IncidentReport to local storage and tracks whether
it's been processed.

Per the master prompt's "SQLite initially" fallback: there is no live
Dataverse Incidents table yet, so this writes to a local SQLite file
instead. Every function is scoped so swapping to a real Dataverse
write-back later only touches THIS file — callers (a future
orchestrator) only ever see log_incident() / get_incident() /
mark_processed(), never raw SQL.

SCOPE NOTE: the master prompt also says this tool "updates the source
Exception record's status to Processed" in Dataverse. That update
belongs to Person A's ingestion layer, which has no live Dataverse
connection and no mock Exception record tied to a generated incident_id
yet. mark_processed() here only updates the local SQLite row for this
incident — wiring it to also flip the source Exception record's status
is explicitly a Phase 2 integration point, not something silently
faked today.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models.incident_report import IncidentReport

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "incident_logger",
        "description": (
            "Logs a completed incident report or marks an existing "
            "incident as processed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["log", "mark_processed"],
                    "description": (
                        "Operation to perform."
                    ),
                },
                "report": {
                    "type": "object",
                    "description": (
                        "IncidentReport required when operation is log."
                    ),
                },
                "incident_id": {
                    "type": "string",
                    "description": (
                        "Existing incident ID required when "
                        "operation is mark_processed."
                    ),
                },
            },
            "required": ["operation"],
        },
    },
}

DEFAULT_DB_PATH = "temp/incidents.db"


class IncidentLoggerError(Exception):
    """Raised when a logging operation fails, e.g. writing to a
    corrupted database file or looking up an incident_id that doesn't
    exist."""


@contextmanager
def _get_connection(db_path: str):
    """
    Opens a SQLite connection, ensuring the parent directory exists
    first (temp/ may not exist yet on a fresh checkout) and the schema
    is created if this is the first write. Closes the connection
    automatically via the context manager, so callers never have to
    remember to.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Creates the incidents table if it doesn't already exist. Safe to
    call on every connection — CREATE TABLE IF NOT EXISTS is a no-op
    once the table is present."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            flow_name TEXT NOT NULL,
            environment TEXT NOT NULL,
            severity TEXT NOT NULL,
            error_category TEXT NOT NULL,
            report_json TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            logged_at TEXT NOT NULL
        )
        """
    )


def log_incident(report: IncidentReport, db_path: str = DEFAULT_DB_PATH) -> str:
    """
    Writes a finished IncidentReport to SQLite and returns its
    generated incident_id.

    A UUID is used (not an auto-increment integer) because a real
    Dataverse write-back will assign a GUID — matching that shape now
    means callers storing this ID don't need to change when the real
    write-back replaces this function's body.

    The full report is stored as JSON (via IncidentReport.model_dump_json())
    in report_json, with a few key fields (flow_name, environment,
    severity, error_category) pulled out into their own columns so they
    can be queried/filtered without deserializing the JSON blob every
    time — e.g. "how many Critical incidents this week" shouldn't
    require parsing every row's full JSON.

    Args:
        report: the validated IncidentReport to log.
        db_path: path to the SQLite file. Defaults to temp/incidents.db.

    Returns:
        The generated incident_id (a UUID string).
    """
    incident_id = str(uuid.uuid4())

    with _get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO incidents
                (incident_id, flow_name, environment, severity,
                 error_category, report_json, processed, logged_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                incident_id,
                report.flow_name,
                report.environment,
                report.severity.value,
                report.error_category.value,
                report.model_dump_json(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return incident_id


def get_incident(incident_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[dict]:
    """
    Retrieves a logged incident by ID, for verification or later
    display. Returns None if no incident with that ID exists, rather
    than raising, since "not found" is an expected outcome for a lookup
    (unlike log_incident or mark_processed, where failure is exceptional).

    Returns a plain dict (parsed from the stored JSON, plus processed
    status), not a re-constructed IncidentReport — the Pydantic model
    guarantees a report is valid *before* it's stored; re-validating on
    every read would be redundant work with no additional safety.
    """
    with _get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT report_json, processed, logged_at FROM incidents "
            "WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()

    if row is None:
        return None

    report_json, processed, logged_at = row
    data = json.loads(report_json)
    data["processed"] = bool(processed)
    data["logged_at"] = logged_at
    return data


def mark_processed(incident_id: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Marks a logged incident as processed.

    Returns True if a row was found and updated, False if no incident
    with that ID exists — a caller can use this to detect a bad/stale
    incident_id without a separate lookup first.

    Scope note: this only updates the local SQLite row. It does NOT
    update any Dataverse Exception record's status, since that
    integration doesn't exist yet (see module docstring).

    Raises:
        IncidentLoggerError: if incident_id is empty/None, which would
            silently match zero rows and be easy to mistake for a
            legitimate "not found."
    """
    if not incident_id:
        raise IncidentLoggerError(
            "mark_processed() requires a non-empty incident_id."
        )

    with _get_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE incidents SET processed = 1 WHERE incident_id = ?",
            (incident_id,),
        )
        return cursor.rowcount > 0


def execute_tool_call(
tool_name: str,
arguments: dict,
) -> dict:
    """Execute incident logging operations from Agent input."""

    if tool_name != TOOL_SCHEMA["function"]["name"]:
        raise ValueError(f"Unknown tool: {tool_name}")

    operation = arguments.get("operation")

    if operation == "log":
        if "report" not in arguments:
            raise ValueError(
                "report is required for log operation"
            )

        report = IncidentReport.model_validate(
            arguments["report"]
        )

        incident_id = log_incident(report)

        return {
            "success": True,
            "incident_id": incident_id,
        }

    if operation == "mark_processed":
        if not arguments.get("incident_id"):
            raise ValueError(
                "incident_id is required for mark_processed"
            )

        success = mark_processed(
            arguments["incident_id"]
        )

        return {
            "success": success,
            "incident_id": arguments["incident_id"],
        }

    raise ValueError(
        "operation must be either 'log' or 'mark_processed'"
    )