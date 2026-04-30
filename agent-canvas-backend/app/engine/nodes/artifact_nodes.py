import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_artifact_store_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        key = config.get("key") or config.get("artifact_key") or config.get("artifactKey") or "artifact"
        state_key = config.get("state_key") or config.get("stateKey") or "current_output"
        output_key = config.get("output_key") or config.get("outputKey") or "current_artifact_id"
        content = _state_value(state, state_key)
        root = Path(config.get("root", "./artifacts"))
        root.mkdir(parents=True, exist_ok=True)

        artifact_id = _artifact_id(key)
        extension = config.get("extension") or config.get("ext") or "txt"
        extension = str(extension).lstrip(".") or "txt"
        path = root / f"{artifact_id}.{extension}"
        path.write_text(_serialize_content(content), encoding="utf-8")

        refs = dict(state.get("artifact_refs", {}))
        ref = {
            "id": artifact_id,
            "key": key,
            "path": str(path),
            "source_key": state_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "content_type": config.get("content_type") or config.get("contentType") or "text/plain",
        }
        refs[artifact_id] = ref
        latest_by_key = dict(state.get("latest_artifacts", {}))
        latest_by_key[key] = artifact_id
        return {
            "artifact_refs": refs,
            "latest_artifacts": latest_by_key,
            output_key: artifact_id,
            **append_trace(
                state,
                config.get("_node_id", "artifact_store"),
                config.get("_label", "Artifact Store"),
                artifact_id=artifact_id,
                key=key,
                path=str(path),
                source_key=state_key,
            ),
        }

    return node


def build_artifact_load_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        key = config.get("key", "artifact")
        artifact_id = config.get("artifact_id") or config.get("artifactId") or _state_value(state, config.get("artifact_id_key") or config.get("artifactIdKey"))
        refs = state.get("artifact_refs", {})
        latest_artifacts = state.get("latest_artifacts", {})
        resolved_id = artifact_id or latest_artifacts.get(key) or key
        ref = refs.get(resolved_id, resolved_id)
        path = Path(config.get("path") or (ref.get("path") if isinstance(ref, dict) else ref or ""))
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        output_key = config.get("output_key") or config.get("outputKey") or "current_output"
        return {
            output_key: content,
            **append_trace(
                state,
                config.get("_node_id", "artifact_load"),
                config.get("_label", "Artifact Load"),
                artifact_id=resolved_id,
                path=str(path),
            ),
        }

    return node


def _artifact_id(key: str) -> str:
    safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(key)).strip("-._") or "artifact"
    return f"{safe_key}-{uuid.uuid4().hex[:12]}"


def _serialize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(content)


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
