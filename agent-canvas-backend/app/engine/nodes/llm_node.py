import json
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
    tool_handling_mode = config.get("tool_handling_mode") or config.get("toolHandlingMode") or "bind-tools"
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
                "node_results": {tool_result_key: output},
                "messages": tool_messages,
                **append_trace(state, node_id, label, output_preview=output[:200]),
            }
            if update_current_output or tool_result_key == "current_output":
                result_updates["current_output"] = output
            return result_updates

        llm = build_chat_model(config)
        tool_server_by_name = {}
        lc_tools = []
        prompt_tool_specs = []
        for tool in auto_tools:
            server_id = _tool_value(tool, "server_id", "serverId")
            tool_name = _tool_value(tool, "tool_name", "name")
            if server_id in mcp_servers:
                await mcp_client.connect(mcp_servers[server_id])
                server_tools = await mcp_client.list_tools(server_id)
                matched = [item for item in server_tools if not tool_name or item.get("name") == tool_name]
                prompt_tool_specs.extend(_tool_prompt_specs(server_id, matched))
                for item in matched:
                    if item.get("name"):
                        tool_server_by_name[item["name"]] = server_id
                if tool_handling_mode == "bind-tools":
                    allowed = {tool_name} if tool_name else None
                    lc_tools.extend(await mcp_client.as_langchain_tools(server_id, allowed_tool_names=allowed))
        if lc_tools and tool_handling_mode == "bind-tools":
            llm = llm.bind_tools(lc_tools)

        messages = []
        system_prompt = config.get("system_prompt") or config.get("systemPrompt")
        if prompt_tool_specs and tool_handling_mode == "prompt-only":
            system_prompt = _append_prompt_tool_specs(system_prompt, prompt_tool_specs, tool_name_key, tool_args_key)
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.extend(state.get("messages", []))
        if state.get("query") and not messages:
            messages.append(HumanMessage(content=state["query"]))
        response = await llm.ainvoke(messages)

        produced_messages = [response]
        for call in getattr(response, "tool_calls", []) or []:
            server_id = call.get("server_id") or config.get("tool_server_id") or config.get("toolServerId") or tool_server_by_name.get(call.get("name"))
            name = call.get("name")
            args = call.get("args") or {}
            if server_id in mcp_servers and name:
                result = await mcp_client.call_tool(server_id, name, args)
                produced_messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", name)))

        output = str(getattr(response, "content", ""))
        parsed_output = _json_object(output)
        node_results = _node_results_from_prompt_output(parsed_output, output, output_key, tool_name_key, tool_args_key)
        updates.update(
            {
                "node_results": node_results,
                "messages": produced_messages or [AIMessage(content=output)],
                **append_trace(state, node_id, label, output_preview=output[:200]),
            }
        )
        if update_current_output or output_key == "current_output":
            updates["current_output"] = str(node_results.get(output_key, output))
        return updates

    return node


def _append_prompt_tool_specs(
    system_prompt: str | None,
    tool_specs: list[dict[str, Any]],
    tool_name_key: str | None,
    tool_args_key: str | None,
) -> str:
    base = system_prompt or ""
    selected_tool_key = tool_name_key or "selected_tool"
    args_key = tool_args_key or "tool_args"
    instruction = (
        "\n\nAvailable MCP tools are listed below. Use these specs to decide the next tool, but do not call tools directly. "
        "Return only a JSON object, with no markdown fences and no prose. "
        f"Put the selected tool name in `{selected_tool_key}`. "
        f"Put tool arguments in `{args_key}` as an object. "
        f"For example: {{\"{selected_tool_key}\": \"tool_name\", \"{args_key}\": {{}}}}.\n"
        f"MCP tool specs:\n{json.dumps(tool_specs, ensure_ascii=False, indent=2)}"
    )
    return base + instruction


def _json_object(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _node_results_from_prompt_output(
    parsed_output: dict[str, Any] | None,
    raw_output: str,
    output_key: str,
    tool_name_key: str | None,
    tool_args_key: str | None,
) -> dict[str, Any]:
    selected_tool_key = tool_name_key or output_key
    args_key = tool_args_key or "tool_args"

    if parsed_output is None:
        updates = {output_key: raw_output}
        if tool_name_key:
            updates[selected_tool_key] = raw_output.strip()
        return updates

    updates: dict[str, Any] = dict(parsed_output)

    if selected_tool_key not in updates:
        for fallback_key in ("tool_name", "toolName", "selected_tool", "current_output", output_key):
            if fallback_key in parsed_output:
                updates[selected_tool_key] = parsed_output[fallback_key]
                break
    if args_key not in updates:
        for fallback_key in ("tool_args", "toolArgs", "parameters", "params", "args", "arguments"):
            if fallback_key in parsed_output:
                updates[args_key] = parsed_output[fallback_key]
                break
    if output_key not in updates:
        updates[output_key] = updates.get(selected_tool_key, raw_output)
    return updates


def _tool_prompt_specs(server_id: str, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = []
    for tool in tools:
        specs.append(
            {
                "serverId": server_id,
                "name": tool.get("name"),
                "description": tool.get("description"),
                "inputSchema": tool.get("inputSchema") or tool.get("input_schema") or tool.get("parameters") or {},
            }
        )
    return specs


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
    return value


def _tool_value(tool: dict[str, Any], snake_key: str, camel_key: str) -> Any:
    return tool.get(snake_key) or tool.get(camel_key)
