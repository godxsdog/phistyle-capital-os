from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AgentMetadata:
    id: str
    name: str
    role: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

