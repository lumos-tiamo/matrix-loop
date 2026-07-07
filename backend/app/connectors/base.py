from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ConnectorResult:
    tier: str                                   # api | scrape | manual
    snapshots: list[dict] = field(default_factory=list)
    content: list[dict] = field(default_factory=list)


class Connector(Protocol):
    tier: str
    def fetch(self, account) -> ConnectorResult: ...


class ManualOnlyError(RuntimeError):
    """Raised when a platform has no automated connector; use CSV import instead."""
