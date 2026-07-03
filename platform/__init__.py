"""PhiStyle OS platform package.

This package intentionally uses the repository's architecture name `platform`.
It also proxies Python's standard-library `platform` module so tooling that
imports `platform.system()` or `platform.python_version()` keeps working.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sysconfig


_stdlib_platform_path = Path(sysconfig.get_paths()["stdlib"]) / "platform.py"
_stdlib_spec = importlib.util.spec_from_file_location("_stdlib_platform", _stdlib_platform_path)
if _stdlib_spec is None or _stdlib_spec.loader is None:
    raise ImportError("Unable to load Python standard-library platform module")

_stdlib_platform = importlib.util.module_from_spec(_stdlib_spec)
_stdlib_spec.loader.exec_module(_stdlib_platform)


def __getattr__(name: str):
    return getattr(_stdlib_platform, name)


for _name in dir(_stdlib_platform):
    if _name.startswith("__"):
        continue
    globals().setdefault(_name, getattr(_stdlib_platform, _name))

