from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class AppStatus(str, Enum):
    ACTIVE = "active"
    FUTURE = "future"
    SCAFFOLD = "scaffold"


class Sensitivity(str, Enum):
    GENERAL = "general"
    MEDICAL = "medical"
    PERSONAL_FINANCE = "personal-finance"
    TRAVEL = "travel"
    SYSTEM = "system"


@dataclass(frozen=True)
class AppMetadata:
    id: str
    name: str
    category: str
    status: AppStatus
    sensitivity: Sensitivity
    route: str
    health_endpoint: str
    owner: str
    data_scope: str

    def to_dict(self) -> dict[str, str]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["sensitivity"] = self.sensitivity.value
        return payload

