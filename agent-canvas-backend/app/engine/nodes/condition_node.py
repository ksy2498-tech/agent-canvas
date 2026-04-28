from typing import Any

from app.engine.nodes._common import SAFE_BUILTINS, append_trace
from app.engine.state import AgentState


def build_condition_node(config: dict[str, Any]):
    async def node_fn(state: AgentState) -> AgentState:
        return append_trace(state, config.get("_node_id", "condition"), config.get("_label", "Condition"))

    async def condition_fn(state: AgentState) -> str:
        expression = config.get("expression", "False")
        value = eval(expression, {"__builtins__": SAFE_BUILTINS}, {"state": state})
        return "true" if bool(value) else "false"

    return node_fn, condition_fn

