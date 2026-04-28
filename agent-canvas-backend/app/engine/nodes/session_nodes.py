import json
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.messages import messages_from_dict, messages_to_dict

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def _db_path(config: dict[str, Any]) -> Path:
    return Path(config.get("path", "./sessions.db"))


def _ensure(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )


def build_session_load_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        path = _db_path(config)
        _ensure(path)
        session_id = state.get("session_id") or config.get("session_id")
        output_key = config.get("output_key", "messages")
        if not session_id:
            return append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"))
        with sqlite3.connect(path) as conn:
            row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"))
        payload = json.loads(row[0])
        value = payload.get(output_key, payload)
        if output_key == "messages":
            value = messages_from_dict(value)
        return {output_key: value, **append_trace(state, config.get("_node_id", "session_load"), config.get("_label", "Session Load"))}

    return node


def build_session_save_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        path = _db_path(config)
        _ensure(path)
        session_id = state.get("session_id") or config.get("session_id")
        keys = config.get("keys", ["messages"])
        if session_id:
            payload = {}
            for key in keys:
                value = state.get(key)
                payload[key] = messages_to_dict(value) if key == "messages" and value else value
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO sessions (session_id, payload) VALUES (?, ?)",
                    (session_id, json.dumps(payload, default=str)),
                )
        return append_trace(state, config.get("_node_id", "session_save"), config.get("_label", "Session Save"))

    return node

