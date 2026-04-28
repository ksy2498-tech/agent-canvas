from pathlib import Path
from typing import Any

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_artifact_store_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        key = config.get("key", "artifact")
        content = state.get(config.get("state_key", "current_output"), "")
        root = Path(config.get("root", "./artifacts"))
        root.mkdir(parents=True, exist_ok=True)
        path = root / key
        path.write_text(str(content), encoding="utf-8")
        refs = dict(state.get("artifact_refs", {}))
        refs[key] = str(path)
        return {
            "artifact_refs": refs,
            **append_trace(state, config.get("_node_id", "artifact_store"), config.get("_label", "Artifact Store"), path=str(path)),
        }

    return node


def build_artifact_load_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        key = config.get("key", "artifact")
        refs = state.get("artifact_refs", {})
        path = Path(config.get("path") or refs.get(key, ""))
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        output_key = config.get("output_key", "current_output")
        return {
            output_key: content,
            **append_trace(state, config.get("_node_id", "artifact_load"), config.get("_label", "Artifact Load"), path=str(path)),
        }

    return node

