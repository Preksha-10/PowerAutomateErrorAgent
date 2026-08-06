"""
config.py

Single source of truth for configuration: paths, log level, mode flags,
and (eventually) Azure credentials.

Loads from a .env file if one exists at the repo root; falls back to
the defaults below if it doesn't. Today the repo has no .env file and
none of the secrets below are real — load_dotenv() is a no-op when no
.env is found, so this must not be required for the project to run.

WHY ONE FILE: every value here would otherwise get hardcoded
independently in whatever module needs it (tools/incident_logger_tool.py
already has its own DEFAULT_DB_PATH, for example). Centralizing means
there's exactly one place to change when we move from mock mode to live
Azure/Dataverse access — not a grep-and-replace across the codebase.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # no-op if no .env file exists — safe on a fresh checkout


# --- Storage -----------------------------------------------------------

INCIDENT_DB_PATH = os.getenv("INCIDENT_DB_PATH", "temp/incidents.db")
"""
Path to the local SQLite incidents database.

NOTE: tools/incident_logger_tool.py currently defines its own
DEFAULT_DB_PATH = "temp/incidents.db" independently of this constant.
The two are kept in sync by value today, but incident_logger_tool.py
should eventually import INCIDENT_DB_PATH from here instead of defining
its own default, so there's a single source of truth rather than two
constants that happen to agree. Left as-is for now, out of this file's
scope — flagging the seam rather than silently duplicating it.
"""


# --- Logging -------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
"""Log level for the whole project, e.g. tools/notification_tool.py's
logger. A future orchestrator should configure logging.basicConfig()
(or similar) once, at startup, using this value — rather than every
module picking its own level independently."""


# --- Dataverse mode --------------------------------------------------------

DATAVERSE_MODE = os.getenv("DATAVERSE_MODE", "mock")
"""
Mirrors services.dataverse_client.DataverseClient's mode parameter
("mock" or "live"). Defaults to "mock" since we have no live Dataverse
access yet. A future orchestrator should read this value and pass it
into DataverseClient(mode=DATAVERSE_MODE, ...) rather than hardcoding
"mock" at the call site, so switching to live mode later is a
config/environment change, not a code change.
"""


# --- Azure credentials (NOT YET USED) --------------------------------------
#
# These are read into constants now so the shape is correct once Phase 2's
# live-mode work begins, but nothing in the codebase reads or uses these
# values yet. Left unset (None) by default — do not assume these are
# populated anywhere in current code.

AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
DATAVERSE_ORG_URL = os.getenv("DATAVERSE_ORG_URL")