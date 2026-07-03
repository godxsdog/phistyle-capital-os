from phistyle_platform.registry.registry import default_registry, list_registered_apps


def test_registry_lists_initial_apps():
    app_ids = {app["id"] for app in list_registered_apps()}

    assert app_ids == {"capital", "points-wallet", "dental-ppt", "travel", "snowboard"}


def test_legacy_apps_are_registered_as_future_only():
    apps = {app["id"]: app for app in list_registered_apps()}

    assert apps["points-wallet"]["status"] == "future"
    assert apps["dental-ppt"]["status"] == "future"


def test_registry_can_get_app_by_id():
    app = default_registry.get_app("capital")

    assert app is not None
    assert app.id == "capital"
