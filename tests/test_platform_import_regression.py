def test_stdlib_platform_is_not_shadowed():
    import platform

    assert platform.python_version()


def test_app_registry_imports_from_phistyle_platform_package():
    from phistyle_platform.registry.registry import list_registered_apps

    assert len(list_registered_apps()) == 5

