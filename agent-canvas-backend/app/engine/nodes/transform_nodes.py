from typing import Any

from app.engine.nodes._common import SAFE_BUILTINS, append_trace, build_mcp_callable_map, maybe_await
from app.engine.state import AgentState


def build_input_transform_node(config: dict[str, Any], mcp_servers: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
        exec(config.get("code", "async def transform(state, mcp):\n    return {}"), namespace)
        transform = namespace.get("transform")
        if not callable(transform):
            raise ValueError("Transform node must define transform(state, mcp)")
        mcp = build_mcp_callable_map(config.get("attached_mcp_tools", []), mcp_servers)
        result = await maybe_await(transform(dict(state), mcp))
        if not isinstance(result, dict):
            raise ValueError("transform() must return a dict")
        result.setdefault("trace", [])
        result["trace"] += append_trace(state, config.get("_node_id", "transform"), config.get("_label", "Input Transform"))["trace"]
        return result

    return node


def build_output_format_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        template = config.get("template", "{current_output}")
        values = dict(state)
        try:
            output = template.format(**values)
        except Exception:
            output = str(state.get("current_output", ""))
        return {
            "current_output": output,
            **append_trace(state, config.get("_node_id", "output_format"), config.get("_label", "Output Format"), output_preview=output[:200]),
        }

    return node

