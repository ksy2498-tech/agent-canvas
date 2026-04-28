from typing import Any

from app.engine.nodes._common import SAFE_BUILTINS, append_trace, build_mcp_callable_map, maybe_await
from app.engine.state import AgentState


def build_code_node(config: dict[str, Any], mcp_servers: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        label = config.get("_label", "Code")
        node_id = config.get("_node_id", label)
        namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
        exec(config.get("code", "async def run(state, mcp):\n    return {}"), namespace)
        run = namespace.get("run")
        if not callable(run):
            raise ValueError("Code node must define run(state, mcp)")
        mcp = build_mcp_callable_map(config.get("attached_mcp_tools", []), mcp_servers)
        result = await maybe_await(run(dict(state), mcp))
        if not isinstance(result, dict):
            raise ValueError("Code node run() must return a dict")
        result.setdefault("trace", [])
        result["trace"] += append_trace(state, node_id, label)["trace"]
        return result

    return node

