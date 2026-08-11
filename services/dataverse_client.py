"""
DataverseClient — single point of contact for retrieving Flows and
Exceptions data. Today: MOCK MODE ONLY, reading from sample_errors/*.json.

DESIGN INTENT: every caller (tools/dataverse_flows_tool.py,
tools/dataverse_exceptions_tool.py) depends only on this class's
get_flows() / get_exceptions() method signatures — never on how the
data is actually fetched. When real Dataverse access exists, only the
inside of this file changes (add a "live" branch that calls the OData
Web API); no calling code anywhere else needs to change.
"""

import json
import os
import time
from typing import List, Optional

import requests

from models.flow_record import FlowRecord
from models.exception_record import ExceptionRecord


try:
    import msal
except Exception:  # pragma: no cover - runtime import guard
    msal = None


class DataverseClient:
    """Client for Flows/Exceptions data, mock-mode only for now.

    mode="mock" (default): reads from local JSON fixture files.
    mode="live": reserved for later — will call the real Dataverse
    OData Web API using this same interface. Callers never need to
    know which mode is active.
    """

    def __init__(
        self,
        mode: str = "mock",
        flows_fixture_path: str = "sample_errors/mock_flows.json",
        exceptions_fixture_path: str = "sample_errors/mock_exceptions.json",
        dataverse_url: Optional[str] = None,
        client_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        if mode not in ("mock", "live"):
            raise ValueError(f"Unsupported mode: {mode}")

        self.mode = mode
        self.flows_fixture_path = flows_fixture_path
        self.exceptions_fixture_path = exceptions_fixture_path

        # Live-mode runtime attrs (only used when mode == "live")
        self.dataverse_url = dataverse_url or os.environ.get("DATAVERSE_URL")
        self.client_id = client_id or os.environ.get("AZURE_CLIENT_ID")
        self.tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID", "organizations")
        self._access_token = None
        self._token_expires_at = 0

        if self.mode == "live":
            # Preserve the original behaviour for the empty-config case
            # (tests expect NotImplementedError when no live config exists).
            has_url = bool(self.dataverse_url)
            has_client = bool(self.client_id) or bool(os.environ.get("AZURE_CLIENT_SECRET"))
            if not (has_url and has_client):
                raise NotImplementedError(
                    "Live Dataverse mode is not implemented yet. "
                    "This is the only method that needs to change when "
                    "real Web API access is available."
                )

            if msal is None:
                raise RuntimeError(
                    "msal package is required for live mode. Install with: pip install msal"
                )

            # Normalize URL (no trailing slash)
            self.dataverse_url = self.dataverse_url.rstrip("/")

            # MSAL authority
            self._authority = f"https://login.microsoftonline.com/{self.tenant_id}"

            # Default scope for Dataverse: {org_url}/.default
            org = self.dataverse_url.replace("https://", "")
            self._scopes = [f"https://{org}/.default"]

            # If a client secret is provided, prefer client-credentials flow
            self.client_secret = os.environ.get("AZURE_CLIENT_SECRET")
            if self.client_secret:
                # Confidential client (app-only)
                self._msal_app = msal.ConfidentialClientApplication(
                    client_id=self.client_id,
                    client_credential=self.client_secret,
                    authority=self._authority,
                )
                self._ensure_token_via_client_credentials()
            else:
                # Public client (interactive device code)
                self._msal_app = msal.PublicClientApplication(
                    self.client_id, authority=self._authority
                )
                # Attempt a device-code interactive authentication now so the
                # client is ready for immediate API calls.
                self._ensure_token_via_device_flow()

    def get_flows(self) -> List[FlowRecord]:
        """Return all flows from the fixture file, parsed into
        FlowRecord objects. In live mode this will become a $select/
        $filter OData GET against the Flows table instead."""
        if self.mode == "mock":
            raw_records = self._load_json(self.flows_fixture_path)
            return [FlowRecord.from_dataverse_dict(r) for r in raw_records]

        # Live mode: not implemented in detail — consumers should use
        # a domain-specific query. Placeholder to avoid silent failures.
        raise NotImplementedError(
            "Live get_flows() is not implemented. Use Dataverse OData queries "
            "via the client._odata_get() helper or implement the entity set name."
        )

    def get_exceptions(self) -> List[ExceptionRecord]:
        """Return all exceptions from the fixture file, parsed into
        ExceptionRecord objects. In live mode this will become a
        $filter=statuscode eq Failed and createdon ge <window> query,
        per the master prompt's cost rule — never pull everything."""
        if self.mode == "mock":
            raw_records = self._load_json(self.exceptions_fixture_path)
            return [ExceptionRecord.from_dataverse_dict(r) for r in raw_records]

        raise NotImplementedError(
            "Live get_exceptions() is not implemented. Use Dataverse OData queries "
            "via the client._odata_get() helper or implement the entity set name."
        )

    def _ensure_token_via_device_flow(self):
        """Initiate MSAL device-code flow and store the access token."""
        # Fast path: still valid
        if self._access_token and time.time() < self._token_expires_at - 30:
            return

        flow = self._msal_app.initiate_device_flow(scopes=self._scopes)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to start device flow: {flow}")

        # Show instructions to the terminal user
        print(flow["message"])  # device code instructions

        result = self._msal_app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Device flow failed: {result}")

        self._access_token = result["access_token"]
        expires_in = int(result.get("expires_in", 3600))
        self._token_expires_at = time.time() + expires_in

        # Optionally store account info
        self._account = result.get("id_token_claims") or {}

    def _get_auth_header(self) -> dict:
        self._ensure_token_via_device_flow()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _ensure_token_via_client_credentials(self):
        """Acquire a token using client credentials (non-interactive)."""
        # Fast path
        if self._access_token and time.time() < self._token_expires_at - 30:
            return

        result = self._msal_app.acquire_token_for_client(scopes=self._scopes)
        if "access_token" not in result:
            raise RuntimeError(f"Client credentials flow failed: {result}")

        self._access_token = result["access_token"]
        expires_in = int(result.get("expires_in", 3600))
        self._token_expires_at = time.time() + expires_in

    def _odata_get(self, path: str, params: Optional[dict] = None) -> dict:
        """Perform a simple GET against the Dataverse Web API (v9.2).

        Args:
            path: OData path *relative* to `/api/data/v9.2/`, e.g. "accounts"
            params: optional query params dict

        Returns:
            Parsed JSON response (dict) from the Dataverse API.
        """
        url = f"{self.dataverse_url}/api/data/v9.2/{path}"
        headers = self._get_auth_header().copy()
        headers["Accept"] = "application/json"
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def who_am_i(self) -> dict:
        """Call the WhoAmI function to identify the current user in Dataverse.

        Returns a dict with the raw response from the WhoAmI endpoint.
        """
        # WhoAmI is a function at the root
        return self._odata_get("WhoAmI()")

    @staticmethod
    def _load_json(path: str) -> list:
        """Isolated so tests can monkeypatch/point this at a temp
        file, and so a bad/missing fixture path fails with a clear
        message instead of a raw FileNotFoundError deep in a test."""
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Mock fixture not found at {path}. "
                f"Expected JSON array of Dataverse-shaped records."
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)