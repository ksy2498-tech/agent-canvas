from typing import Any

from app.engine.nodes._common import append_trace, runtime_from_config
from app.engine.nodes.code_sandbox import run_user_code_subprocess
from app.engine.state import AgentState


def build_code_node(config: dict[str, Any], mcp_servers: dict[str, Any]):
    async def node(state: AgentState, run_config: dict[str, Any] | None = None) -> AgentState:
        label = config.get("_label", "Code")
        node_id = config.get("_node_id", label)
        runtime = runtime_from_config(run_config)
        timeout_seconds = float(config.get("timeoutSeconds") or config.get("timeout_seconds") or 5)
        result, updated_runtime = await run_user_code_subprocess(
            code=config.get("code", "async def run(state, mcp, runtime):\n    return {}"),
            state=dict(state),
            runtime=runtime,
            function_name="run",
            timeout_seconds=timeout_seconds,
        )
        runtime.clear()
        runtime.update(updated_runtime)
        result.setdefault("trace", [])
        result["trace"] += append_trace(state, node_id, label, isolated=True)["trace"]
        return result

    return node
