from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: str
    agent_id: str
    run_id: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

