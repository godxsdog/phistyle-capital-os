import pytest


def test_backend_root_packages_are_importable_without_backend_dependencies():
    import phistyle_platform.runtime.runtime  # noqa: F401
    import services.llm_router.router  # noqa: F401
    import shared.models.agent  # noqa: F401


def test_backend_app_imports_when_dependencies_are_available():
    pytest.importorskip("fastapi")

    import backend.app.main  # noqa: F401
