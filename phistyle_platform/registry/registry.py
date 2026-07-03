from __future__ import annotations

from phistyle_platform.registry.default_apps import DEFAULT_APPS
from phistyle_platform.registry.types import AppMetadata


class AppRegistry:
    def __init__(self, apps: tuple[AppMetadata, ...] = DEFAULT_APPS) -> None:
        self._apps = apps

    def list_apps(self) -> list[AppMetadata]:
        return list(self._apps)

    def get_app(self, app_id: str) -> AppMetadata | None:
        return next((app for app in self._apps if app.id == app_id), None)

    def as_dicts(self) -> list[dict[str, str]]:
        return [app.to_dict() for app in self._apps]


default_registry = AppRegistry()


def list_registered_apps() -> list[dict[str, str]]:
    return default_registry.as_dicts()

