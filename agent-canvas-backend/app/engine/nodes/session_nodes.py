import json
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.messages import messages_from_dict, messages_to_dict

from app.engine.nodes._common import SAFE_BUILTINS, append_trace, runtime_from_config, write_runtime
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


def _deserialize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _deserialize_value(key, value)
        for key, value in payload.items()
    }


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
    async def node(state: AgentState, run_config: dict[str, Any] | None = None) -> AgentState:
        path = _db_path(config)
        _ensure(path)
        session_id = _session_id(config, state)
        target = config.get("target") or config.get("outputTarget") or "runtime"
        output_key = config.get("output_key") or config.get("outputKey") or "session"
        if not session_id:
            return append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"))
        with sqlite3.connect(path) as conn:
            row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"), session_id=session_id, loaded=False)
        payload = json.loads(row[0])
        loaded_session = {"session_id": session_id, **_deserialize_payload(payload)}
        if target in {"runtime", "both"}:
            runtime = runtime_from_config(run_config)
            write_runtime(runtime, "session", output_key, loaded_session)
        updates: AgentState = {}
        if target in {"state", "both"}:
            state_key = output_key if output_key.startswith("metadata.") or output_key.startswith("node_results.") else f"metadata.{output_key}"
            _assign_path(updates, state_key, _session_summary(loaded_session))
        updates.update(
            append_trace(
                state,
                config.get("_node_id", "session_load"),
                config.get("_label", "Session Load"),
                session_id=session_id,
                loaded=True,
                target=target,
                output_key=output_key,
            )
        )
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


def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session.get("session_id"),
        "keys": sorted(session.keys()),
        "message_count": len(session.get("messages") or []),
        "node_result_keys": sorted((session.get("node_results") or {}).keys()) if isinstance(session.get("node_results"), dict) else [],
    }


def _keys_to_save(config: dict[str, Any], state: AgentState) -> list[str]:
    raw_keys = config.get("keys") or config.get("keysToSave") or ["messages", "node_results", "metadata", "artifacts"]
    keys = [key for key in raw_keys if key]
    if not keys:
        return ["messages", "node_results", "metadata", "artifacts"]
    if "metadata" in keys and "node_results" not in keys and state.get("node_results"):
        keys.append("node_results")
    return keys
