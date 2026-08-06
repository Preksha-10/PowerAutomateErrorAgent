"""
tests/test_config.py

Tests for config.py.
Verifies that defaults apply when no .env file / no environment
variables are set, and that environment variables override those
defaults when present — the two behaviors load_dotenv() + os.getenv()
are relied on to provide.

Reloads the config module under controlled environment conditions
rather than importing it once at module load time, since config.py
reads os.environ at IMPORT time (module-level constants) — a single
top-level import wouldn't let us test both the "no override" and
"override present" cases in the same test run.
"""

import importlib
import os

import config


def test_defaults_apply_when_no_env_vars_set(monkeypatch):
    """
    With no relevant environment variables set, config.py's constants
    should equal the hardcoded defaults — this is what makes the
    project runnable on a fresh checkout with zero .env file.
    """
    monkeypatch.delenv("INCIDENT_DB_PATH", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DATAVERSE_MODE", raising=False)

    importlib.reload(config)

    assert config.INCIDENT_DB_PATH == "temp/incidents.db"
    assert config.LOG_LEVEL == "INFO"
    assert config.DATAVERSE_MODE == "mock"


def test_env_vars_override_defaults(monkeypatch):
    """
    Setting environment variables (as a .env file, loaded via
    load_dotenv(), effectively does) should override the hardcoded
    defaults — proving config.py actually reads the environment rather
    than just returning fixed values regardless of what's set.
    """
    monkeypatch.setenv("INCIDENT_DB_PATH", "/custom/path/incidents.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATAVERSE_MODE", "live")

    importlib.reload(config)

    assert config.INCIDENT_DB_PATH == "/custom/path/incidents.db"
    assert config.LOG_LEVEL == "DEBUG"
    assert config.DATAVERSE_MODE == "live"

    # Clean up: reload once more with the env vars removed so later
    # tests in the same session see defaults again, not this test's
    # overrides leaking through the module-level cache.
    monkeypatch.delenv("INCIDENT_DB_PATH", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DATAVERSE_MODE", raising=False)
    importlib.reload(config)


def test_azure_credential_placeholders_are_none_by_default(monkeypatch):
    """
    The Azure credential placeholders must default to None (not, say,
    empty strings or a placeholder value that could be mistaken for a
    real one) when unset — these are explicitly not-yet-used, and a
    truthy-but-fake default would be easy to accidentally treat as
    "configured" later.
    """
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("DATAVERSE_ORG_URL", raising=False)

    importlib.reload(config)

    assert config.AZURE_TENANT_ID is None
    assert config.AZURE_CLIENT_ID is None
    assert config.AZURE_CLIENT_SECRET is None
    assert config.DATAVERSE_ORG_URL is None