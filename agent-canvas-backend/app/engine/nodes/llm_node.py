from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.engine.llm_provider import build_chat_model
from app.engine.nodes._common import append_trace
from app.engine.state import AgentState
from app.mcp.client import mcp_client


def build_llm_node(config: dict[str, Any], mcp_servers: dict[str, Any]):
    attached_tools = config.get("attached_mcp_tools") or config.get("attachedTools") or []
    auto_tools = [tool for tool in attached_tools if _tool_value(tool, "execution_mode", "executionMode") == "auto"]
    tool_only = [tool for tool in attached_tools if _tool_value(tool, "execution_mode", "executionMode") == "tool-only"]
    output_key = config.get("output_key") or config.get("outputKey") or "current_output"
    tool_result_key = config.get("tool_result_key") or config.get("toolResultKey") or output_key
    tool_name_key = config.get("tool_name_key") or config.get("toolNameKey")
    tool_args_key = config.get("tool_args_key") or config.get("toolArgsKey")
    update_current_output = config.get("update_current_output")
    if update_current_output is None:
        update_current_output = config.get("updateCurrentOutput", True)

    async def node(state: AgentState) -> AgentState:
        label = config.get("_label", "LLM")
        node_id = config.get("_node_id", label)
        updates: AgentState = {}
        tool_messages = []

        for tool in _select_tool_only_tools(tool_only, state, tool_name_key):
            server_id = _tool_value(tool, "server_id", "serverId")
            tool_name = _tool_value(tool, "tool_name", "name")
            if server_id in mcp_servers and tool_name:
                await mcp_client.connect(mcp_servers[server_id])
                args = _tool_args(state, config, tool_args_key)
                result = await mcp_client.call_tool(server_id, tool_name, args)
                tool_messages.append(ToolMessage(content=str(result), tool_call_id=f"{server_id}:{tool_name}"))
        if tool_only and not auto_tools:
            output = "\n".join(message.content for message in tool_messages)
            result_updates: AgentState = {
                tool_result_key: output,
                "messages": tool_messages,
                **append_trace(state, node_id, label, output_preview=output[:200]),
            }
            if update_current_output or tool_result_key == "current_output":
                result_updates["current_output"] = output
            return result_updates

        llm = build_chat_model(config)
        lc_tools = []
        for tool in auto_tools:
            server_id = _tool_value(tool, "server_id", "serverId")
            if server_id in mcp_servers:
                await mcp_client.connect(mcp_servers[server_id])
                lc_tools.extend(await mcp_client.as_langchain_tools(server_id))
        if lc_tools:
            llm = llm.bind_tools(lc_tools)

        messages = []
        system_prompt = config.get("system_prompt") or config.get("systemPrompt")
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.extend(state.get("messages", []))
        if state.get("query") and not messages:
            messages.append(HumanMessage(content=state["query"]))
        response = await llm.ainvoke(messages)

        produced_messages = [response]
        for call in getattr(response, "tool_calls", []) or []:
            server_id = call.get("server_id") or config.get("tool_server_id") or config.get("toolServerId")
            name = call.get("name")
            args = call.get("args") or {}
            if server_id in mcp_servers and name:
                result = await mcp_client.call_tool(server_id, name, args)
                produced_messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", name)))

        output = str(getattr(response, "content", ""))
        updates.update(
            {
                output_key: output,
                "messages": produced_messages or [AIMessage(content=output)],
                **append_trace(state, node_id, label, output_preview=output[:200]),
            }
        )
        if update_current_output or output_key == "current_output":
            updates["current_output"] = output
        return updates

    return node


def _select_tool_only_tools(tools: list[dict[str, Any]], state: AgentState, tool_name_key: str | None) -> list[dict[str, Any]]:
    selected = str(_state_value(state, tool_name_key) or "").strip() if tool_name_key else ""
    if not selected:
        return tools
    return [tool for tool in tools if str(_tool_value(tool, "tool_name", "name") or "").strip() == selected]


def _tool_args(state: AgentState, config: dict[str, Any], tool_args_key: str | None) -> dict[str, Any]:
    if tool_args_key:
        value = _state_value(state, tool_args_key)
        if isinstance(value, dict):
            return value
    value = config.get("tool_args") or config.get("toolArgs") or {}
    return value if isinstance(value, dict) else {}


def _state_value(state: AgentState, key: str | None) -> Any:
    if not key:
        return None
    value: Any = state
    for part in str(key).split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _tool_value(tool: dict[str, Any], snake_key: str, camel_key: str) -> Any:
    return tool.get(snake_key) or tool.get(camel_key)
