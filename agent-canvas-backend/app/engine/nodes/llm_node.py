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

    async def node(state: AgentState) -> AgentState:
        label = config.get("_label", "LLM")
        node_id = config.get("_node_id", label)
        updates: AgentState = {}
        tool_messages = []

        for tool in tool_only:
            server_id = _tool_value(tool, "server_id", "serverId")
            tool_name = _tool_value(tool, "tool_name", "name")
            if server_id in mcp_servers and tool_name:
                await mcp_client.connect(mcp_servers[server_id])
                result = await mcp_client.call_tool(server_id, tool_name, config.get("tool_args", {}))
                tool_messages.append(ToolMessage(content=str(result), tool_call_id=f"{server_id}:{tool_name}"))
        if tool_only and not auto_tools:
            output = "\n".join(message.content for message in tool_messages)
            return {
                "current_output": output,
                "messages": tool_messages,
                **append_trace(state, node_id, label, output_preview=output[:200]),
            }

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
            server_id = call.get("server_id") or config.get("tool_server_id")
            name = call.get("name")
            args = call.get("args") or {}
            if server_id in mcp_servers and name:
                result = await mcp_client.call_tool(server_id, name, args)
                produced_messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", name)))

        output = str(getattr(response, "content", ""))
        updates.update(
            {
                "current_output": output,
                "messages": produced_messages or [AIMessage(content=output)],
                **append_trace(state, node_id, label, output_preview=output[:200]),
            }
        )
        return updates

    return node


def _tool_value(tool: dict[str, Any], snake_key: str, camel_key: str) -> Any:
    return tool.get(snake_key) or tool.get(camel_key)
