from __future__ import annotations


class SchedulerPlaceholder:
    """Future scheduling hook. No background jobs are implemented yet."""

    def list_schedules(self) -> list[dict[str, str]]:
        return []

