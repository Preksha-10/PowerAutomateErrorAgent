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
from typing import List

from models.flow_record import FlowRecord
from models.exception_record import ExceptionRecord


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
    ):
        if mode not in ("mock", "live"):
            raise ValueError(f"Unsupported mode: {mode}")
        if mode == "live":
            # Intentionally not implemented yet — fail loudly rather
            # than silently falling back to mock data, which would
            # hide a config mistake once we do have real credentials.
            raise NotImplementedError(
                "Live Dataverse mode is not implemented yet. "
                "This is the only method that needs to change when "
                "real Web API access is available."
            )
        self.mode = mode
        self.flows_fixture_path = flows_fixture_path
        self.exceptions_fixture_path = exceptions_fixture_path

    def get_flows(self) -> List[FlowRecord]:
        """Return all flows from the fixture file, parsed into
        FlowRecord objects. In live mode this will become a $select/
        $filter OData GET against the Flows table instead."""
        raw_records = self._load_json(self.flows_fixture_path)
        return [FlowRecord.from_dataverse_dict(r) for r in raw_records]

    def get_exceptions(self) -> List[ExceptionRecord]:
        """Return all exceptions from the fixture file, parsed into
        ExceptionRecord objects. In live mode this will become a
        $filter=statuscode eq Failed and createdon ge <window> query,
        per the master prompt's cost rule — never pull everything."""
        raw_records = self._load_json(self.exceptions_fixture_path)
        return [ExceptionRecord.from_dataverse_dict(r) for r in raw_records]

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