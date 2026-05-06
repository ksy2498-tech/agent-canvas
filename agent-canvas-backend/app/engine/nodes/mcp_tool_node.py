from typing import Any

from app.engine.nodes._common import append_trace, runtime_from_config, write_runtime
from app.engine.nodes.state_path import runtime_result_key, state_value, tool_args, tool_value
from app.engine.state import AgentState
from app.mcp.client import mcp_client


def build_mcp_tool_node(config: dict[str, Any], mcp_servers: dict[str, Any]):
    attached_tools = config.get("attached_mcp_tools") or config.get("attachedTools") or []
    tool_name_key = config.get("tool_name_key") or config.get("toolNameKey")
    tool_args_key = config.get("tool_args_key") or config.get("toolArgsKey")
    tool_result_key = runtime_result_key(config.get("tool_result_key") or config.get("toolResultKey") or "tool_result")
    result_target = config.get("result_target") or config.get("resultTarget") or "runtime"
    update_current_output = config.get("update_current_output")
    if update_current_output is None:
        update_current_output = config.get("updateCurrentOutput", result_target in {"state", "both"})

    async def node(state: AgentState, run_config: dict[str, Any] | None = None) -> AgentState:
        label = config.get("_label", "MCP Tool Call")
        node_id = config.get("_node_id", label)
        tool = _select_tool(attached_tools, state, tool_name_key)
        if not tool:
            raise ValueError("No MCP tool selected. Attach a tool or set a valid Tool name state key.")

        server_id = tool_value(tool, "server_id", "serverId")
        tool_name = tool_value(tool, "tool_name", "name")
        if not server_id or server_id not in mcp_servers:
            raise ValueError(f"MCP server not found for tool {tool_name or '<unknown>'}")
        if not tool_name:
            raise ValueError("MCP tool name is missing")

        await mcp_client.connect(mcp_servers[server_id])
        args = tool_args(state, config, tool_args_key)
        result = await mcp_client.call_tool(server_id, tool_name, args)
        output = result if isinstance(result, str) else str(result)
        updates: AgentState = {}
        if result_target in {"runtime", "both"}:
            runtime = runtime_from_config(run_config)
            write_runtime(runtime, "tool_results", tool_result_key, result)
            updates["runtime_updates"] = {"tool_results": {tool_result_key: result}}
        if result_target in {"state", "both"}:
            updates["node_results"] = {tool_result_key: result}
        if update_current_output or tool_result_key == "current_output":
            updates["current_output"] = output
        updates.update(
            append_trace(
                state,
                node_id,
                label,
                tool=tool_name,
                output_preview=output[:200],
                result_target=result_target,
                result_key=tool_result_key,
            )
        )
        return updates

    return node


def _select_tool(tools: list[dict[str, Any]], state: AgentState, tool_name_key: str | None) -> dict[str, Any] | None:
    selected = str(state_value(state, tool_name_key) or "").strip() if tool_name_key else ""
    if selected:
        return next((tool for tool in tools if str(tool_value(tool, "tool_name", "name") or "").strip() == selected), None)
    return tools[0] if tools else None
