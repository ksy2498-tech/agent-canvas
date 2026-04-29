import json
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.messages import messages_from_dict, messages_to_dict

from app.engine.nodes._common import SAFE_BUILTINS, append_trace
from app.engine.state import AgentState


def _db_path(config: dict[str, Any]) -> Path:
    return Path(config.get("path", "./sessions.db"))


def _ensure(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )


def _session_id(config: dict[str, Any], state: AgentState) -> str | None:
    expression = config.get("session_id_expression") or config.get("sessionIdExpression")
    if expression:
        value = eval(expression, {"__builtins__": SAFE_BUILTINS}, {"state": state})
        if value is not None:
            return str(value)
    value = state.get("session_id") or config.get("session_id") or config.get("sessionId") or state.get("query")
    return str(value) if value else None


def _state_value(state: AgentState, key: str | None) -> Any:
    if not key:
        return None
    direct = _path_value(state, key)
    if direct is not None:
        return direct
    return _path_value(state.get("node_results", {}), key)


def _path_value(value: Any, key: str | None) -> Any:
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


def _serialize_value(key: str, value: Any) -> Any:
    return messages_to_dict(value) if key == "messages" and value else value


def _deserialize_value(key: str, value: Any) -> Any:
    return messages_from_dict(value) if key == "messages" and isinstance(value, list) else value


def _merge_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "messages" and isinstance(merged.get(key), list) and isinstance(value, list):
            merged[key] = [*merged[key], *value]
        elif isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_payload(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_session_load_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        path = _db_path(config)
        _ensure(path)
        session_id = _session_id(config, state)
        output_key = config.get("output_key") or config.get("outputKey") or "messages"
        if not session_id:
            return append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"))
        with sqlite3.connect(path) as conn:
            row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"))
        payload = json.loads(row[0])
        if output_key in {"*", "__all__", "state"}:
            return {**{key: _deserialize_value(key, value) for key, value in payload.items()}, **append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"), session_id=session_id)}
        value = _path_value(payload, output_key)
        if value is None:
            return {
                **{key: _deserialize_value(key, item) for key, item in payload.items()},
                **append_trace(
                    state,
                    config.get("_node_id", "session_load"),
                    config.get("_label", "Session Load"),
                    session_id=session_id,
                    loaded="payload",
                    missing_key=output_key,
                ),
            }
        value = _deserialize_value(output_key, value)
        updates: AgentState = {}
        _assign_path(updates, output_key, value)
        updates.update(append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"), session_id=session_id))
        return updates

    return node


def build_session_save_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        path = _db_path(config)
        _ensure(path)
        session_id = _session_id(config, state)
        keys = _keys_to_save(config, state)
        if not session_id:
            return append_trace(state, config.get("_node_id", "session_save"), config.get("_label", "Session Save"), status="skipped", reason="missing session_id")
        payload = {}
        for key in keys:
            value = _state_value(state, key)
            _assign_path(payload, key, _serialize_value(key, value))
        with sqlite3.connect(path) as conn:
            if (config.get("mode") or "overwrite") == "append":
                row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
                if row:
                    payload = _merge_payload(json.loads(row[0]), payload)
            conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, payload) VALUES (?, ?)",
                (session_id, json.dumps(payload, default=str)),
            )
        return append_trace(state, config.get("_node_id", "session_save"), config.get("_label", "Session Save"), session_id=session_id, saved_keys=keys)

    return node


def _keys_to_save(config: dict[str, Any], state: AgentState) -> list[str]:
    raw_keys = config.get("keys") or config.get("keysToSave") or ["messages", "node_results"]
    keys = [key for key in raw_keys if key]
    if not keys:
        return ["messages", "node_results"]
    if "metadata" in keys and "node_results" not in keys and state.get("node_results"):
        keys.append("node_results")
    return keys
