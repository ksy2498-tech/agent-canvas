import json
from typing import Any

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_state_set_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        values = config.get("values", config.get("state", {}))
        updates = _values_to_state(values)
        updates.update(append_trace(state, config.get("_node_id", "state_set"), config.get("_label", "State Set")))
        return updates

    return node


def build_state_get_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        key = config.get("key")
        alias = config.get("output_alias") or key
        updates = {alias: state.get(key)} if key else {}
        updates.update(append_trace(state, config.get("_node_id", "state_get"), config.get("_label", "State Get")))
        return updates

    return node


def _values_to_state(values: Any) -> dict[str, Any]:
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
        _assign_path(updates, key, _typed_value(row.get("value"), row.get("type")))
    return updates


def _typed_value(value: Any, value_type: str | None) -> Any:
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


def _assign_path(target: dict[str, Any], key: str, value: Any) -> None:
    parts = str(key).split(".")
    cursor = target
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value
