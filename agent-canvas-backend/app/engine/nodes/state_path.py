import json
from typing import Any

from app.engine.state import AgentState


def path_value(value: Any, key: str | None) -> Any:
    if not key:
        return None
    for part in str(key).split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return value


def state_value(state: AgentState, key: str | None) -> Any:
    if not key:
        return None
    direct = path_value(state, key)
    if direct is not None:
        return direct
    return path_value(state.get("node_results", {}), key)


def assign_path(target: dict[str, Any], key: str, value: Any) -> None:
    cursor = target
    parts = str(key).split(".")
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def typed_value(value: Any, value_type: str | None) -> Any:
    if value_type == "number":
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        return int(number) if number.is_integer() else number
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "json":
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
    return value


def values_to_state(values: Any) -> dict[str, Any]:
    if isinstance(values, dict):
        return values
    if not isinstance(values, list):
        return {}
    updates: dict[str, Any] = {}
    for row in values:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        if not key:
            continue
        assign_path(updates, key, typed_value(row.get("value"), row.get("type")))
    return updates


def tool_value(tool: dict[str, Any], snake_key: str, camel_key: str) -> Any:
    return tool.get(snake_key) or tool.get(camel_key)


def tool_args(state: AgentState, config: dict[str, Any], tool_args_key: str | None) -> dict[str, Any]:
    if tool_args_key:
        value = state_value(state, tool_args_key)
        if isinstance(value, dict):
            return value
    value = config.get("tool_args") or config.get("toolArgs") or {}
    return value if isinstance(value, dict) else {}


def runtime_result_key(key: str) -> str:
    return "tool_result" if key in {"tool_results", "runtime.tool_results"} else key
