from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import ast

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal local envs
    yaml = None


CONFIG_DIR = Path(__file__).resolve().parent / "config"
DEFAULT_PROVIDER_CONFIG = CONFIG_DIR / "llm_providers.yaml"
DEFAULT_ROUTING_CONFIG = CONFIG_DIR / "llm_routing.yaml"
DEFAULT_RETRY_CONFIG = CONFIG_DIR / "llm_retry.yaml"
DEFAULT_PRICING_CONFIG = CONFIG_DIR / "llm_pricing.yaml"


def load_yaml_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        raw = handle.read()
    if yaml is None:
        return _load_simple_yaml_mapping(raw)
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def _load_simple_yaml_mapping(raw: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    for raw_line in raw.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            item_text = line[2:]
            if not isinstance(parent, list):
                raise ValueError("List item found outside list")
            if ": " in item_text or item_text.endswith(":"):
                key, value = _split_key_value(item_text)
                item: dict[str, Any] = {}
                parent.append(item)
                if value is None:
                    item[key] = {}
                    stack.append((indent, item))
                    stack.append((indent + 2, item[key]))
                else:
                    item[key] = _parse_scalar(value)
                    stack.append((indent, item))
            else:
                parent.append(_parse_scalar(item_text))
            continue

        key, value = _split_key_value(line)
        if value is None:
            next_container: dict[str, Any] | list[Any]
            next_container = [] if _next_nonempty_line_is_list(raw, raw_line) else {}
            parent[key] = next_container
            stack.append((indent, next_container))
        else:
            parent[key] = _parse_scalar(value)
    return root


def _next_nonempty_line_is_list(raw: str, current_line: str) -> bool:
    lines = raw.splitlines()
    try:
        index = lines.index(current_line)
    except ValueError:
        return False
    current_indent = len(current_line) - len(current_line.lstrip(" "))
    for line in lines[index + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        return indent > current_indent and line.strip().startswith("- ")
    return False


def _split_key_value(line: str) -> tuple[str, str | None]:
    if ":" not in line:
        raise ValueError(f"Expected key/value line: {line}")
    key, value = line.split(":", 1)
    value = value.strip()
    return key.strip(), value if value else None


def _parse_scalar(value: str) -> Any:
    if value in {"true", "false"}:
        return value == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value == "":
        return ""
    if value == "null":
        return None
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [_parse_scalar(item.strip()) for item in inner.split(",")]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


@lru_cache(maxsize=1)
def load_provider_config() -> dict[str, Any]:
    return load_yaml_config(DEFAULT_PROVIDER_CONFIG)


@lru_cache(maxsize=1)
def load_routing_config() -> dict[str, Any]:
    return load_yaml_config(DEFAULT_ROUTING_CONFIG)


@lru_cache(maxsize=1)
def load_retry_config() -> dict[str, Any]:
    return load_yaml_config(DEFAULT_RETRY_CONFIG)


@lru_cache(maxsize=1)
def load_pricing_config() -> dict[str, Any]:
    return load_yaml_config(DEFAULT_PRICING_CONFIG)


def provider_config(provider_id: str) -> dict[str, Any]:
    providers = load_provider_config().get("providers", {})
    return dict(providers[provider_id])


def routing_config(route_name: str) -> dict[str, Any]:
    routes = load_routing_config().get("routes", {})
    return dict(routes[route_name])


def first_matching_role_route(role: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    routes = load_routing_config().get("role_routes", [])
    fallback: dict[str, Any] | None = None
    for route in routes:
        match = route.get("match", {})
        if match.get("role") == "*":
            fallback = route
            continue
        if match.get("role") != role:
            continue
        if all(context.get(key) == value for key, value in match.items() if key != "role"):
            return dict(route)
    if fallback is None:
        raise ValueError("llm_routing.yaml must define a fallback rule")
    return dict(fallback)
