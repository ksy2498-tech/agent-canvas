from typing import Any

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_state_set_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        values = config.get("values", config.get("state", {}))
        updates = dict(values)
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

