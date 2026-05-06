import io
import json
import re
import textwrap
import zipfile
from typing import Any

from app.codegen.export_runtime import EXPORT_RUNTIME_PY


def generate_zip(graph: Any, nodes: list[Any], edges: list[Any], mcp_servers: list[Any] | None = None) -> bytes:
    graph_spec = _graph_spec(graph, nodes, edges, mcp_servers or [])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("agent.py", _agent_py(graph_spec))
        archive.writestr("agent_runtime.py", EXPORT_RUNTIME_PY)
        archive.writestr("graph_spec.json", json.dumps(graph_spec, ensure_ascii=False, indent=2, default=str))
        archive.writestr(".env.example", _env_example(nodes))
        archive.writestr("requirements.txt", _requirements(nodes))
        archive.writestr("README.md", _readme(graph))
    return buffer.getvalue()


def _graph_spec(graph: Any, nodes: list[Any], edges: list[Any], mcp_servers: list[Any]) -> dict[str, Any]:
    return {
        "id": getattr(graph, "id", None),
        "name": getattr(graph, "name", "Agent Canvas Export"),
        "nodes": [
            {
                "id": node.id,
                "type": node.node_type,
                "label": node.label,
                "config": node.config or {},
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "source": edge.source_node_id,
                "target": edge.target_node_id,
                "sourceHandle": edge.source_handle or "",
                "targetHandle": edge.target_handle or "",
                "conditionLabel": edge.condition_label,
            }
            for edge in edges
        ],
        "mcpServers": [
            {
                "id": server.id,
                "name": server.name,
                "scope": server.scope,
                "transport": server.transport,
                "config": server.config or {},
            }
            for server in mcp_servers
        ],
    }


def _agent_py(graph_spec: dict[str, Any]) -> str:
    graph_json = json.dumps(graph_spec, ensure_ascii=False, default=str)
    return textwrap.dedent(
        f'''
        import asyncio
        import ast
        import json
        import operator
        import os
        import re
        import sqlite3
        import uuid
        from datetime import datetime, timezone
        from pathlib import Path
        from typing import Annotated, Any, TypedDict

        import httpx
        from agent_runtime import (
            SAFE_BUILTINS,
            AgentState,
            append_trace,
            assign_path,
            make_runtime,
            maybe_await,
            merge_dicts,
            read_runtime,
            runtime_result_key,
            state_value,
            tool_args,
            tool_value,
            typed_value,
            values_to_state,
            run_user_code_subprocess,
        )
        from dotenv import load_dotenv
        from fastmcp import Client
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, messages_from_dict, messages_to_dict
        from langchain_core.tools import StructuredTool
        from langgraph.graph import END, START, StateGraph
        from sqlalchemy import create_engine, text

        load_dotenv()

        GRAPH_SPEC = json.loads({graph_json!r})

        MCP_SERVERS = {{server["id"]: server for server in GRAPH_SPEC.get("mcpServers", [])}}
        MCP_CONNECTIONS: dict[str, tuple[dict[str, Any], Client]] = {{}}


        def generated_state_schema():
            annotations: dict[str, Any] = {{
                "query": str,
                "messages": Annotated[list[Any], operator.add],
                "current_output": str,
                "node_results": Annotated[dict, merge_dicts],
                "metadata": Annotated[dict, merge_dicts],
                "runtime": Annotated[dict, merge_dicts],
                "session_id": str | None,
                "artifacts": Annotated[dict, merge_dicts],
                "trace": Annotated[list[dict], operator.add],
                "db_result": Any,
                "http_result": Any,
            }}
            for key in dynamic_state_keys():
                top_key = top_level_key(key)
                if top_key and top_key not in annotations:
                    annotations[top_key] = Any
            return TypedDict("GeneratedState", annotations, total=False)


        def dynamic_state_keys() -> set[str]:
            keys = set()
            for node in GRAPH_SPEC.get("nodes", []):
                config = node.get("config") or {{}}
                node_type = str(node.get("type") or "").lower()
                if node_type in {{"llm", "llmnode"}}:
                    keys.add(config.get("output_key") or config.get("outputKey") or "current_output")
                    keys.add(config.get("tool_name_key") or config.get("toolNameKey"))
                    keys.add(config.get("tool_args_key") or config.get("toolArgsKey"))
                if node_type in {{"code", "codenode"}}:
                    keys.update(returned_dict_keys(config.get("code") or ""))
                if node_type in {{"stateset", "state_set"}}:
                    values = config.get("values") or config.get("state") or {{}}
                    if isinstance(values, dict):
                        keys.update(values.keys())
                    elif isinstance(values, list):
                        keys.update(row.get("key") for row in values if isinstance(row, dict) and row.get("key"))
                if node_type in {{"stateget", "state_get"}}:
                    key = config.get("key")
                    keys.add(config.get("output_alias") or config.get("outputAlias") or key)
                if node_type in {{"runtimeset", "runtime_set"}}:
                    pass
                if node_type in {{"runtimeget", "runtime_get"}}:
                    target_scope = config.get("targetScope") or config.get("target_scope") or "state"
                    if target_scope != "runtime":
                        keys.add(config.get("outputKey") or config.get("output_key") or "current_output")
                if node_type in {{"dbquery", "db_query"}}:
                    keys.add(config.get("output_key", "db_result"))
                    keys.add("db_result")
                if node_type in {{"artifactstore", "artifact_store"}}:
                    output_key = config.get("output_key") or config.get("outputKey") or "artifacts.current_id"
                    keys.add(output_key)
                if node_type in {{"artifactload", "artifact_load"}}:
                    target_scope = config.get("target_scope") or config.get("targetScope") or "state"
                    if target_scope != "runtime":
                        keys.add(config.get("output_key") or config.get("outputKey") or "current_output")
                if node_type in {{"http", "httprequest", "http_request"}}:
                    keys.add(config.get("outputKey") or config.get("output_key") or "http_result")
                    keys.add("http_result")
                if node_type in {{"inputtransform", "input_transform"}}:
                    keys.update(config.get("declared_output_keys") or config.get("declaredOutputKeys") or [])
                    keys.update(returned_dict_keys(config.get("code") or ""))
                if node_type in {{"outputformat", "output_format"}}:
                    keys.add("current_output")
            return {{str(key) for key in keys if key}}


        def top_level_key(key: Any) -> str:
            return str(key or "").split(".", 1)[0].strip()


        def returned_dict_keys(code: str) -> set[str]:
            try:
                tree = ast.parse(code or "")
            except SyntaxError:
                return set()
            keys: set[str] = set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
                    continue
                for key_node in node.value.keys:
                    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                        keys.add(key_node.value)
            return keys


        def attached_tools(config: dict[str, Any]) -> list[dict[str, Any]]:
            return config.get("attached_mcp_tools") or config.get("attachedTools") or []


        def fastmcp_config(server: dict[str, Any]) -> dict[str, Any]:
            name = server.get("name") or server["id"]
            config = server.get("config") or {{}}
            if server.get("transport") == "stdio":
                if not config.get("command"):
                    raise ValueError("stdio MCP server requires config.command")
                server_config = {{
                    "transport": "stdio",
                    "command": config.get("command"),
                    "args": config.get("args", []),
                }}
                if config.get("env"):
                    server_config["env"] = config["env"]
                if config.get("cwd"):
                    server_config["cwd"] = config["cwd"]
            elif server.get("transport") in {{"sse", "streamable-http"}}:
                if not config.get("url"):
                    raise ValueError(f"{{server.get('transport')}} MCP server requires config.url")
                server_config = {{
                    "transport": server.get("transport"),
                    "url": config.get("url"),
                    "headers": config.get("headers", {{}}),
                }}
            else:
                raise ValueError(f"Unsupported MCP transport: {{server.get('transport')}}")
            return {{"mcpServers": {{name: server_config}}}}


        async def connect_mcp(server_id: str) -> Client:
            if server_id in MCP_CONNECTIONS:
                return MCP_CONNECTIONS[server_id][1]
            server = MCP_SERVERS.get(server_id)
            if not server:
                raise ValueError(f"MCP server {{server_id}} is not included in this export")
            client = Client(fastmcp_config(server))
            await client.__aenter__()
            MCP_CONNECTIONS[server_id] = (server, client)
            return client


        async def close_mcp_connections() -> None:
            for _, client in list(MCP_CONNECTIONS.values()):
                await client.__aexit__(None, None, None)
            MCP_CONNECTIONS.clear()


        def serialize(value: Any) -> Any:
            if hasattr(value, "model_dump"):
                return serialize(value.model_dump())
            if isinstance(value, dict):
                return {{key: serialize(item) for key, item in value.items()}}
            if isinstance(value, list):
                return [serialize(item) for item in value]
            if isinstance(value, tuple):
                return [serialize(item) for item in value]
            if hasattr(value, "data"):
                return serialize(value.data)
            if hasattr(value, "content"):
                return serialize(value.content)
            if hasattr(value, "text"):
                return value.text
            return value


        async def call_mcp_tool(server_id: str, tool_name: str, args: dict[str, Any] | None = None) -> Any:
            client = await connect_mcp(server_id)
            return serialize(await client.call_tool(tool_name, args or {{}}))


        def build_chat_model(config: dict[str, Any], temperature: float | int | None = None):
            provider = str(config.get("provider") or "OpenAI").lower()
            model = config.get("model") or default_model(provider)
            api_key = config.get("api_key") or config.get("apiKey")
            base_url = config.get("base_url") or config.get("baseUrl")
            temperature = config.get("temperature", 0 if temperature is None else temperature)
            if provider in {{"openai", "custom"}}:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(model=model, temperature=temperature, api_key=api_key, base_url=base_url or None)
            if provider in {{"gemini", "google", "google gemini"}}:
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=api_key)
            if provider in {{"claude", "anthropic"}}:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)
            raise ValueError(f"Unsupported LLM provider: {{config.get('provider')}}")


        def default_model(provider: str) -> str:
            if provider in {{"gemini", "google", "google gemini"}}:
                return "gemini-2.5-flash-lite"
            if provider in {{"claude", "anthropic"}}:
                return "claude-3-5-haiku-latest"
            return "gpt-oss-120b"


        async def mcp_tool_specs(server_id: str, tool_name: str | None = None) -> list[dict[str, Any]]:
            saved_specs = []
            for node in GRAPH_SPEC.get("nodes", []):
                for tool in attached_tools(node.get("config") or {{}}):
                    saved_server_id = tool_value(tool, "server_id", "serverId")
                    saved_name = tool_value(tool, "tool_name", "name")
                    if saved_server_id != server_id:
                        continue
                    if tool_name and saved_name != tool_name:
                        continue
                    if saved_name:
                        saved_specs.append(
                            {{
                                "name": saved_name,
                                "description": tool.get("description"),
                                "inputSchema": tool.get("inputSchema") or tool.get("input_schema") or tool.get("parameters") or {{}},
                            }}
                        )
            if saved_specs:
                return saved_specs
            client = await connect_mcp(server_id)
            raw_tools = await client.list_tools()
            tools = serialize(raw_tools)
            if isinstance(tools, dict):
                tools = tools.get("tools") or tools.get("data") or []
            if not isinstance(tools, list):
                tools = []
            matched = []
            for item in tools:
                if hasattr(item, "model_dump"):
                    item = item.model_dump()
                if not isinstance(item, dict):
                    item = serialize(item)
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if tool_name and name != tool_name:
                    continue
                matched.append(item)
            return matched


        def tool_prompt_specs(server_id: str, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {{
                    "serverId": server_id,
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "inputSchema": tool.get("inputSchema") or tool.get("input_schema") or tool.get("parameters") or {{}},
                }}
                for tool in tools
            ]


        async def langchain_mcp_tools(config: dict[str, Any], selected_tools: list[dict[str, Any]]) -> tuple[list[Any], dict[str, str], list[dict[str, Any]]]:
            lc_tools = []
            server_by_tool_name = {{}}
            prompt_specs = []
            for tool in selected_tools:
                server_id = tool_value(tool, "server_id", "serverId")
                name = tool_value(tool, "tool_name", "name")
                if not server_id or server_id not in MCP_SERVERS:
                    continue
                matched = await mcp_tool_specs(server_id, name)
                if not matched and name:
                    matched = [{{"name": name, "description": tool.get("description") or f"MCP tool {{name}}", "inputSchema": tool.get("input_schema") or tool.get("inputSchema") or {{}}}}]
                prompt_specs.extend(tool_prompt_specs(server_id, matched))
                for item in matched:
                    item_name = item.get("name")
                    if not item_name:
                        continue
                    server_by_tool_name[item_name] = server_id
                    description = item.get("description") or f"MCP tool {{item_name}}"

                    async def _call(payload: dict[str, Any] | None = None, *, _server_id=server_id, _name=item_name) -> Any:
                        return await call_mcp_tool(_server_id, _name, payload or {{}})

                    lc_tools.append(StructuredTool.from_function(coroutine=_call, name=item_name, description=description))
            return lc_tools, server_by_tool_name, prompt_specs


        def append_prompt_tool_specs(system_prompt: str | None, specs: list[dict[str, Any]], tool_name_key: str | None, tool_args_key: str | None) -> str:
            base = system_prompt or ""
            selected_tool_key = tool_name_key or "selected_tool"
            args_key = tool_args_key or "tool_args"
            instruction = (
                "\\n\\nAvailable MCP tools are listed below. Use these specs to decide the next tool, but do not call tools directly. "
                "Return only a JSON object, with no markdown fences and no prose. "
                f"Put the selected tool name in `{{selected_tool_key}}`. "
                f"Put tool arguments in `{{args_key}}` as an object. "
                f"For example: {{json.dumps({{selected_tool_key: 'tool_name', args_key: {{}}}}, ensure_ascii=False)}}.\\n"
                f"MCP tool specs:\\n{{json.dumps(specs, ensure_ascii=False, indent=2)}}"
            )
            return base + instruction


        def json_object(content: str) -> dict[str, Any] | None:
            text_value = content.strip()
            if text_value.startswith("```"):
                lines = text_value.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text_value = "\\n".join(lines).strip()
            try:
                value = json.loads(text_value)
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None


        def node_results_from_prompt_output(
            parsed_output: dict[str, Any] | None,
            raw_output: str,
            output_key: str,
            tool_name_key: str | None,
            tool_args_key: str | None,
        ) -> dict[str, Any]:
            selected_tool_key = tool_name_key or output_key
            args_key = tool_args_key or "tool_args"
            if parsed_output is None:
                updates = {{output_key: raw_output}}
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


        def select_tool_only_tools(tools: list[dict[str, Any]], state: AgentState, tool_name_key: str | None) -> list[dict[str, Any]]:
            selected = str(state_value(state, tool_name_key) or "").strip() if tool_name_key else ""
            if not selected:
                return tools
            return [tool for tool in tools if str(tool_value(tool, "tool_name", "name") or "").strip() == selected]


        def stringify_input(value: Any) -> str:
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value, ensure_ascii=False, default=str)
            except TypeError:
                return str(value)


        async def run_llm_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            node_id = node["id"]
            label = node.get("label") or "LLM"
            attached = attached_tools(config)
            auto_tools = [tool for tool in attached if tool_value(tool, "execution_mode", "executionMode") == "auto"]
            tool_only = [tool for tool in attached if tool_value(tool, "execution_mode", "executionMode") == "tool-only"]
            input_key = config.get("input_key") or config.get("inputKey") or "query"
            output_key = config.get("output_key") or config.get("outputKey") or "current_output"
            tool_result_key = config.get("tool_result_key") or config.get("toolResultKey") or output_key
            tool_name_key = config.get("tool_name_key") or config.get("toolNameKey")
            tool_args_key = config.get("tool_args_key") or config.get("toolArgsKey")
            tool_handling_mode = config.get("tool_handling_mode") or config.get("toolHandlingMode") or "bind-tools"
            update_current_output = config.get("update_current_output")
            if update_current_output is None:
                update_current_output = config.get("updateCurrentOutput", True)

            tool_messages = []
            for tool in select_tool_only_tools(tool_only, state, tool_name_key):
                server_id = tool_value(tool, "server_id", "serverId")
                tool_name = tool_value(tool, "tool_name", "name")
                if server_id in MCP_SERVERS and tool_name:
                    args = tool_args(state, config, tool_args_key)
                    result = await call_mcp_tool(server_id, tool_name, args)
                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=f"{{server_id}}:{{tool_name}}"))
            if tool_only and not auto_tools:
                output = "\\n".join(message.content for message in tool_messages)
                updates: AgentState = {{
                    "node_results": {{tool_result_key: output}},
                    "messages": tool_messages,
                    **append_trace(node_id, label, output_preview=output[:200]),
                }}
                if update_current_output or tool_result_key == "current_output":
                    updates["current_output"] = output
                return updates

            llm = build_chat_model(config)
            lc_tools, server_by_tool_name, prompt_specs = await langchain_mcp_tools(config, auto_tools)
            if lc_tools and tool_handling_mode == "bind-tools":
                llm = llm.bind_tools(lc_tools)

            messages = []
            system_prompt = config.get("system_prompt") or config.get("systemPrompt")
            if prompt_specs and tool_handling_mode == "prompt-only":
                system_prompt = append_prompt_tool_specs(system_prompt, prompt_specs, tool_name_key, tool_args_key)
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.extend(state.get("messages", []))
            input_value = state_value(state, input_key)
            if input_value is not None:
                messages.append(HumanMessage(content=stringify_input(input_value)))
            elif state.get("query") and not messages:
                messages.append(HumanMessage(content=state["query"]))

            response = await llm.ainvoke(messages)
            produced_messages = [response]
            for call in getattr(response, "tool_calls", []) or []:
                name = call.get("name")
                server_id = call.get("server_id") or config.get("tool_server_id") or config.get("toolServerId") or server_by_tool_name.get(name or "")
                if server_id and name:
                    result = await call_mcp_tool(server_id, name, call.get("args") or {{}})
                    produced_messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", name)))

            output = str(getattr(response, "content", ""))
            parsed_output = json_object(output)
            node_results = node_results_from_prompt_output(parsed_output, output, output_key, tool_name_key, tool_args_key)
            updates: AgentState = {{
                "node_results": node_results,
                "messages": produced_messages or [AIMessage(content=output)],
                **append_trace(node_id, label, output_preview=output[:200], input_key=input_key),
            }}
            if update_current_output or output_key == "current_output":
                updates["current_output"] = str(node_results.get(output_key, output))
            return updates


        async def run_mcp_tool_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            node_id = node["id"]
            label = node.get("label") or "MCP Tool Call"
            tools = attached_tools(config)
            selected = str(state_value(state, config.get("toolNameKey") or config.get("tool_name_key")) or "").strip()
            tool = next((item for item in tools if str(tool_value(item, "tool_name", "name") or "").strip() == selected), None) if selected else (tools[0] if tools else None)
            if not tool:
                raise ValueError("No MCP tool selected")
            server_id = tool_value(tool, "server_id", "serverId")
            tool_name = tool_value(tool, "tool_name", "name")
            if not server_id or server_id not in MCP_SERVERS:
                raise ValueError(f"MCP server not found for tool {{tool_name or '<unknown>'}}")
            if not tool_name:
                raise ValueError("MCP tool name is missing")
            args_key = config.get("toolArgsKey") or config.get("tool_args_key")
            args = tool_args(state, config, args_key)
            result = await call_mcp_tool(server_id, tool_name, args)
            result_key = runtime_result_key(config.get("toolResultKey") or config.get("tool_result_key") or "tool_result")
            result_target = config.get("resultTarget") or config.get("result_target") or "runtime"
            output = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
            updates: AgentState = {{}}
            if result_target in {{"runtime", "both"}}:
                updates["runtime"] = {{"tool_results": {{result_key: result}}}}
            if result_target in {{"state", "both"}}:
                updates["node_results"] = {{result_key: result}}
            update_current_output = config.get("update_current_output")
            if update_current_output is None:
                update_current_output = config.get("updateCurrentOutput", result_target in {{"state", "both"}})
            if update_current_output or result_key == "current_output":
                updates["current_output"] = output
            updates.update(append_trace(node_id, label, tool=tool_name, output_preview=output[:200], result_target=result_target, result_key=result_key))
            return updates


        async def run_code_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            runtime = state.setdefault("runtime", make_runtime())
            timeout_seconds = float(config.get("timeoutSeconds") or config.get("timeout_seconds") or 5)
            result, updated_runtime = await run_user_code_subprocess(
                code=config.get("code", "async def run(state, mcp, runtime):\\n    return {{}}"),
                state=dict(state),
                runtime=runtime,
                timeout_seconds=timeout_seconds,
            )
            runtime.clear()
            runtime.update(updated_runtime)
            result.setdefault("trace", [])
            result["trace"] += append_trace(node["id"], node.get("label") or "Code")["trace"]
            return result


        def build_mcp_callable_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {{}}
            for tool in attached_tools(config):
                server_id = tool_value(tool, "server_id", "serverId")
                tool_name = tool_value(tool, "tool_name", "name")
                if not server_id or not tool_name:
                    continue
                server_name = MCP_SERVERS.get(server_id, {{}}).get("name") or server_id

                async def _call(args: dict[str, Any] | None = None, *, _server_id=server_id, _tool_name=tool_name) -> Any:
                    return await call_mcp_tool(_server_id, _tool_name, args or {{}})

                result.setdefault(server_name, {{}})[tool_name] = _call
            return result


        def session_db_path(config: dict[str, Any]) -> Path:
            return Path(config.get("path", "./sessions.db"))


        def ensure_session_db(path: Path) -> None:
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")


        def session_id(config: dict[str, Any], state: AgentState) -> str | None:
            expression = config.get("session_id_expression") or config.get("sessionIdExpression")
            if expression:
                value = eval(expression, {{"__builtins__": SAFE_BUILTINS}}, {{"state": state}})
                if value is not None:
                    return str(value)
            value = state.get("session_id") or config.get("session_id") or config.get("sessionId") or state.get("query")
            return str(value) if value else None


        def serialize_session_value(key: str, value: Any) -> Any:
            return messages_to_dict(value) if key == "messages" and value else value


        def deserialize_session_value(key: str, value: Any) -> Any:
            return messages_from_dict(value) if key == "messages" and isinstance(value, list) else value


        def deserialize_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
            return {{key: deserialize_session_value(key, value) for key, value in payload.items()}}


        def merge_session_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
            merged = dict(existing)
            for key, value in incoming.items():
                if key == "messages" and isinstance(merged.get(key), list) and isinstance(value, list):
                    merged[key] = [*merged[key], *value]
                elif isinstance(merged.get(key), dict) and isinstance(value, dict):
                    merged[key] = merge_session_payload(merged[key], value)
                else:
                    merged[key] = value
            return merged


        def session_summary(session: dict[str, Any]) -> dict[str, Any]:
            return {{
                "session_id": session.get("session_id"),
                "keys": sorted(session.keys()),
                "message_count": len(session.get("messages") or []),
                "node_result_keys": sorted((session.get("node_results") or {{}}).keys()) if isinstance(session.get("node_results"), dict) else [],
            }}


        def session_keys_to_save(config: dict[str, Any], state: AgentState) -> list[str]:
            raw_keys = config.get("keys") or config.get("keysToSave") or ["messages", "node_results", "metadata", "artifacts"]
            keys = [key for key in raw_keys if key]
            if not keys:
                return ["messages", "node_results", "metadata", "artifacts"]
            if "metadata" in keys and "node_results" not in keys and state.get("node_results"):
                keys.append("node_results")
            return keys


        async def run_session_load_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            path = session_db_path(config)
            ensure_session_db(path)
            sid = session_id(config, state)
            target = config.get("target") or config.get("outputTarget") or "runtime"
            output_key = config.get("output_key") or config.get("outputKey") or "session"
            label = node.get("label") or "Session Load"
            if not sid:
                return append_trace(node["id"], label)
            with sqlite3.connect(path) as conn:
                row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (sid,)).fetchone()
            if not row:
                return append_trace(node["id"], label, session_id=sid, loaded=False)
            payload = json.loads(row[0])
            loaded_session = {{"session_id": sid, **deserialize_session_payload(payload)}}
            updates: AgentState = {{}}
            if target in {{"runtime", "both"}}:
                updates["runtime"] = {{"session": {{output_key: loaded_session}}}}
            if target in {{"state", "both"}}:
                state_key = output_key if output_key.startswith("metadata.") or output_key.startswith("node_results.") else f"metadata.{{output_key}}"
                assign_path(updates, state_key, session_summary(loaded_session))
            updates.update(append_trace(node["id"], label, session_id=sid, loaded=True, target=target, output_key=output_key))
            return updates


        async def run_session_save_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            path = session_db_path(config)
            ensure_session_db(path)
            sid = session_id(config, state)
            keys = session_keys_to_save(config, state)
            label = node.get("label") or "Session Save"
            if not sid:
                return append_trace(node["id"], label, status="skipped", reason="missing session_id")
            payload: dict[str, Any] = {{}}
            for key in keys:
                assign_path(payload, key, serialize_session_value(key, state_value(state, key)))
            with sqlite3.connect(path) as conn:
                if (config.get("mode") or "overwrite") == "append":
                    row = conn.execute("SELECT payload FROM sessions WHERE session_id = ?", (sid,)).fetchone()
                    if row:
                        payload = merge_session_payload(json.loads(row[0]), payload)
                conn.execute("INSERT OR REPLACE INTO sessions (session_id, payload) VALUES (?, ?)", (sid, json.dumps(payload, default=str)))
            return append_trace(node["id"], label, session_id=sid, saved_keys=keys)


        async def run_state_set_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            updates = values_to_state(config.get("values") or config.get("state") or {{}})
            updates.update(append_trace(node["id"], node.get("label") or "State Set"))
            return updates


        async def run_state_get_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            key = config.get("key")
            alias = config.get("output_alias") or config.get("outputAlias") or key
            updates = {{alias: state_value(state, key)}} if key else {{}}
            updates.update(append_trace(node["id"], node.get("label") or "State Get"))
            return updates

        async def run_runtime_set_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            section = config.get("section") or "scratch"
            key = config.get("key") or "value"
            source_scope = config.get("sourceScope") or config.get("source_scope") or "literal"
            source_key = config.get("sourceKey") or config.get("source_key")
            runtime = state.get("runtime") or make_runtime()
            if source_scope == "state":
                value = state_value(state, source_key)
            elif source_scope == "runtime":
                source_section, _, nested_key = str(source_key or "").partition(".")
                value = read_runtime(runtime, source_section, nested_key or None)
            else:
                value = typed_value(config.get("value"), config.get("valueType") or config.get("value_type"))
            return {{"runtime": {{section: {{key: value}}}}, **append_trace(node["id"], node.get("label") or "Runtime Set", section=section, key=key)}}


        async def run_runtime_get_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            runtime = state.get("runtime") or make_runtime()
            section = config.get("section") or "scratch"
            key = config.get("key") or "value"
            target_scope = config.get("targetScope") or config.get("target_scope") or "state"
            output_key = config.get("outputKey") or config.get("output_key") or "current_output"
            value = read_runtime(runtime, section, key)
            updates: AgentState = {{}}
            if target_scope == "runtime":
                target_section = config.get("targetSection") or config.get("target_section") or "scratch"
                updates["runtime"] = {{target_section: {{output_key: value}}}}
            else:
                assign_path(updates, output_key, value)
            updates.update(append_trace(node["id"], node.get("label") or "Runtime Get", section=section, key=key, target_scope=target_scope, output_key=output_key))
            return updates


        def interpolate(value: Any, state: AgentState) -> Any:
            if isinstance(value, str):
                def repl(match):
                    key = match.group(1)
                    cursor: Any = state
                    for part in key.split("."):
                        cursor = cursor.get(part) if isinstance(cursor, dict) else getattr(cursor, part, "")
                    return str(cursor)

                return re.sub(r"{{state\\.([^}}]+)}}", repl, value)
            if isinstance(value, dict):
                return {{key: interpolate(item, state) for key, item in value.items()}}
            if isinstance(value, list):
                return [interpolate(item, state) for item in value]
            return value


        async def run_http_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            method = config.get("method", "GET")
            url = interpolate(config.get("url", ""), state)
            if not url:
                raise ValueError("HTTP node requires url")
            async with httpx.AsyncClient(timeout=config.get("timeout", 30)) as client:
                response = await client.request(
                    method,
                    url,
                    headers=interpolate(config.get("headers", {{}}), state),
                    params=interpolate(config.get("params", {{}}), state),
                    json=interpolate(config.get("json"), state) if "json" in config else None,
                    data=interpolate(config.get("body"), state) if "body" in config else None,
                )
            try:
                body = response.json()
            except ValueError:
                body = response.text
            result = {{"status_code": response.status_code, "headers": dict(response.headers), "body": body}}
            output_key = config.get("output_key") or config.get("outputKey") or "http_result"
            return {{output_key: result, "http_result": result, **append_trace(node["id"], node.get("label") or "HTTP", status_code=response.status_code)}}


        async def run_db_query_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            alias = config.get("connection_alias")
            connection = None
            for graph_node in GRAPH_SPEC.get("nodes", []):
                node_config = graph_node.get("config") or {{}}
                if graph_node.get("type") in {{"DBConnection", "db_connection"}} and node_config.get("alias") == alias:
                    connection = node_config
                    break
            if connection is None:
                connection = config
            url = connection.get("url") or connection.get("database_url")
            if not url:
                raise ValueError("DB query node requires connection url/database_url")
            engine = create_engine(url.replace("+aiosqlite", ""), future=True)
            with engine.begin() as conn:
                result = conn.execute(text(config.get("query", "")), config.get("params", {{}}))
                rows = [dict(row._mapping) for row in result] if result.returns_rows else []
            output_key = config.get("output_key", "db_result")
            return {{output_key: rows, "db_result": rows, **append_trace(node["id"], node.get("label") or "DB Query", row_count=len(rows))}}


        def artifact_id(key: str) -> str:
            safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(key)).strip("-._") or "artifact"
            return f"{{safe_key}}-{{uuid.uuid4().hex[:12]}}"


        def artifacts_state(state: AgentState) -> dict[str, Any]:
            artifacts = dict(state.get("artifacts", {{}}) or {{}})
            refs = dict(artifacts.get("refs", {{}}) or {{}})
            latest_by_key = dict(artifacts.get("latest_by_key", {{}}) or {{}})
            refs.update(state.get("artifact_refs", {{}}) or {{}})
            latest_by_key.update(state.get("latest_artifacts", {{}}) or {{}})
            current_id = artifacts.get("current_id") or state.get("current_artifact_id")
            return {{"current_id": current_id, "refs": refs, "latest_by_key": latest_by_key}}


        def serialize_artifact_content(content: Any) -> str:
            if isinstance(content, str):
                return content
            try:
                return json.dumps(content, ensure_ascii=False, indent=2, default=str)
            except TypeError:
                return str(content)


        def read_scoped_value(state: AgentState, scope: str, key: str | None) -> Any:
            if scope == "runtime":
                runtime = state.get("runtime") or make_runtime()
                section, _, nested_key = str(key or "").partition(".")
                return read_runtime(runtime, section, nested_key or None)
            return state_value(state, key)


        async def run_artifact_store_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            key = config.get("key") or config.get("artifact_key") or config.get("artifactKey") or "artifact"
            source_scope = config.get("source_scope") or config.get("sourceScope") or "state"
            source_key = config.get("state_key") or config.get("stateKey") or config.get("sourceKey") or "current_output"
            output_key = config.get("output_key") or config.get("outputKey") or "artifacts.current_id"
            content = read_scoped_value(state, source_scope, source_key)
            root = Path(config.get("root", "./artifacts"))
            root.mkdir(parents=True, exist_ok=True)
            aid = artifact_id(key)
            extension = str(config.get("extension") or config.get("ext") or "txt").lstrip(".") or "txt"
            path = root / f"{{aid}}.{{extension}}"
            path.write_text(serialize_artifact_content(content), encoding="utf-8")
            artifacts = artifacts_state(state)
            refs = dict(artifacts.get("refs", {{}}))
            latest_by_key = dict(artifacts.get("latest_by_key", {{}}))
            ref = {{
                "id": aid,
                "key": key,
                "path": str(path),
                "source_scope": source_scope,
                "source_key": source_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "content_type": config.get("content_type") or config.get("contentType") or "text/plain",
            }}
            refs[aid] = ref
            latest_by_key[key] = aid
            updates: AgentState = {{
                "artifacts": {{"current_id": aid, "refs": refs, "latest_by_key": latest_by_key}},
                "runtime": {{"artifacts": {{aid: ref}}}},
            }}
            if output_key and output_key != "artifacts.current_id":
                assign_path(updates, output_key, aid)
            updates.update(append_trace(node["id"], node.get("label") or "Artifact Store", artifact_id=aid, key=key, path=str(path), source_scope=source_scope, source_key=source_key))
            return updates


        async def run_artifact_load_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            key = config.get("key", "artifact")
            target_scope = config.get("target_scope") or config.get("targetScope") or "state"
            artifact_id_key = config.get("artifact_id_key") or config.get("artifactIdKey")
            aid = config.get("artifact_id") or config.get("artifactId") or state_value(state, artifact_id_key)
            artifacts = artifacts_state(state)
            refs = artifacts.get("refs", {{}})
            latest_by_key = artifacts.get("latest_by_key", {{}})
            resolved_id = aid or latest_by_key.get(key) or artifacts.get("current_id") or key
            ref = refs.get(resolved_id, resolved_id)
            path = Path(config.get("path") or (ref.get("path") if isinstance(ref, dict) else ref or ""))
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            output_key = config.get("output_key") or config.get("outputKey") or "current_output"
            updates: AgentState = {{}}
            if target_scope == "runtime":
                updates["runtime"] = {{"scratch": {{output_key: content}}}}
            else:
                assign_path(updates, output_key, content)
            updates.update(append_trace(node["id"], node.get("label") or "Artifact Load", artifact_id=resolved_id, target_scope=target_scope, output_key=output_key, path=str(path)))
            return updates


        async def run_input_transform_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            namespace: dict[str, Any] = {{"__builtins__": SAFE_BUILTINS}}
            exec(config.get("code", "async def transform(state, mcp):\\n    return {{}}"), namespace)
            transform = namespace.get("transform")
            if not callable(transform):
                raise ValueError("Transform node must define transform(state, mcp)")
            result = await maybe_await(transform(dict(state), build_mcp_callable_map(config)))
            if not isinstance(result, dict):
                raise ValueError("transform() must return a dict")
            result.setdefault("trace", [])
            result["trace"] += append_trace(node["id"], node.get("label") or "Input Transform")["trace"]
            return result


        async def run_output_format_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            template = config.get("template", "{{current_output}}")
            values = dict(state)
            try:
                output = template.format(**values)
            except Exception:
                output = str(state.get("current_output", ""))
            return {{"current_output": output, **append_trace(node["id"], node.get("label") or "Output Format", output_preview=output[:200])}}


        def analyze_tokens(text_value: str, engine: str) -> tuple[list[dict[str, Any]], str | None]:
            if engine == "kiwi":
                try:
                    from kiwipiepy import Kiwi

                    kiwi = Kiwi()
                    return [
                        {{"form": token.form, "pos": token.tag, "start": token.start, "len": token.len}}
                        for token in kiwi.tokenize(text_value)
                    ], None
                except Exception as exc:
                    return regex_tokens(text_value), f"Kiwi unavailable: {{exc}}"
            return regex_tokens(text_value), f"Unsupported engine `{{engine}}`; used regex fallback"


        def regex_tokens(text_value: str) -> list[dict[str, Any]]:
            return [{{"form": token, "pos": "UNK"}} for token in re.findall(r"\\w+", text_value)]


        def nlp_summary(result: dict[str, Any]) -> dict[str, Any]:
            return {{
                "engine": result.get("engine"),
                "analysis_type": result.get("analysis_type"),
                "input_key": result.get("input_key"),
                "token_count": len(result.get("tokens") or []),
                "noun_count": len(result.get("nouns") or []),
                "nouns_sample": (result.get("nouns") or [])[:10],
                "fallback": result.get("fallback"),
                "fallback_reason": result.get("fallback_reason"),
            }}


        async def run_nlp_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            input_key = config.get("input_key") or config.get("inputKey") or "current_output"
            text_input = state_value(state, input_key) or state.get("query", "")
            engine = str(config.get("engine", "kiwi")).lower()
            analysis_type = config.get("analysis_type") or config.get("analysisType") or "morpheme"
            result_target = config.get("result_target") or config.get("resultTarget") or "runtime"
            output_key = config.get("output_key") or config.get("outputKey") or "nlp_result"
            summary_key = config.get("summary_key") or config.get("summaryKey") or "metadata.nlp_summary"
            tokens, fallback_reason = analyze_tokens(str(text_input), engine)
            nouns = [item["form"] for item in tokens if str(item.get("pos", "")).startswith("N")]
            result = {{"engine": engine, "analysis_type": analysis_type, "input_key": input_key, "text": str(text_input), "tokens": tokens, "nouns": nouns, "fallback": fallback_reason is not None, "fallback_reason": fallback_reason}}
            updates: AgentState = {{}}
            if result_target in {{"runtime", "both"}}:
                updates["runtime"] = {{"nlp": {{output_key: result}}}}
            if result_target in {{"state", "both"}}:
                assign_path(updates, output_key, result)
            if result_target == "runtime" and summary_key:
                assign_path(updates, summary_key, nlp_summary(result))
            updates.update(append_trace(node["id"], node.get("label") or "NLP", engine=engine, analysis_type=analysis_type, input_key=input_key, result_target=result_target, result_key=output_key, token_count=len(tokens), noun_count=len(nouns), fallback=fallback_reason is not None))
            return updates


        async def run_passthrough_node(node: dict[str, Any], state: AgentState) -> AgentState:
            return append_trace(node["id"], node.get("label") or node.get("type") or "Node")


        async def run_node(node: dict[str, Any], state: AgentState) -> AgentState:
            node_type = str(node.get("type") or "").lower()
            if node_type in {{"start", "end"}}:
                return append_trace(node["id"], node.get("label") or node_type)
            if node_type in {{"llm", "llmnode"}}:
                return await run_llm_node(node, state)
            if node_type in {{"mcptool", "mcp_tool", "mcptoolcall", "mcp_tool_call"}}:
                return await run_mcp_tool_node(node, state)
            if node_type in {{"code", "codenode"}}:
                return await run_code_node(node, state)
            if node_type in {{"sessionload", "session_load"}}:
                return await run_session_load_node(node, state)
            if node_type in {{"sessionsave", "session_save"}}:
                return await run_session_save_node(node, state)
            if node_type in {{"stateset", "state_set"}}:
                return await run_state_set_node(node, state)
            if node_type in {{"stateget", "state_get"}}:
                return await run_state_get_node(node, state)
            if node_type in {{"runtimeset", "runtime_set"}}:
                return await run_runtime_set_node(node, state)
            if node_type in {{"runtimeget", "runtime_get"}}:
                return await run_runtime_get_node(node, state)
            if node_type in {{"dbquery", "db_query"}}:
                return await run_db_query_node(node, state)
            if node_type in {{"artifactstore", "artifact_store"}}:
                return await run_artifact_store_node(node, state)
            if node_type in {{"artifactload", "artifact_load"}}:
                return await run_artifact_load_node(node, state)
            if node_type in {{"http", "httprequest", "http_request"}}:
                return await run_http_node(node, state)
            if node_type in {{"inputtransform", "input_transform"}}:
                return await run_input_transform_node(node, state)
            if node_type in {{"outputformat", "output_format"}}:
                return await run_output_format_node(node, state)
            if node_type in {{"nlp", "nlpnode"}}:
                return await run_nlp_node(node, state)
            return await run_passthrough_node(node, state)


        async def route_condition(node: dict[str, Any], state: AgentState) -> str:
            config = node.get("config") or {{}}
            node_type = str(node.get("type") or "").lower()
            if node_type in {{"condition", "conditionnode"}}:
                expression = config.get("expression", "False")
                value = eval(expression, {{"__builtins__": SAFE_BUILTINS}}, {{"state": state}})
                return "true" if bool(value) else "false"
            if node_type in {{"router", "routernode"}}:
                routes = config.get("routes") or config.get("conditions") or []
                text = str(state.get("current_output") or state.get("query", ""))
                lower = text.lower()
                for route in routes:
                    label = route.get("label") or route.get("condition_label")
                    keywords = route.get("keywords", [])
                    if any(str(keyword).lower() in lower for keyword in keywords):
                        return label
                return config.get("default_route") or (routes[0].get("label") if routes else "default")
            return "default"


        def node_name(node_id: str) -> str:
            return "node_" + node_id.replace("-", "_")


        def build_graph():
            GeneratedState = generated_state_schema()
            builder = StateGraph(GeneratedState)
            nodes = GRAPH_SPEC.get("nodes", [])
            edges = GRAPH_SPEC.get("edges", [])
            node_by_id = {{node["id"]: node for node in nodes}}

            for node in nodes:
                async def _runner(state, _node=node):
                    return await run_node(_node, state)
                builder.add_node(node_name(node["id"]), _runner)

            first = next((node for node in nodes if str(node.get("type", "")).lower() == "start"), nodes[0] if nodes else None)
            if first:
                builder.add_edge(START, node_name(first["id"]))
            else:
                builder.add_edge(START, END)

            conditional_types = {{"condition", "conditionnode", "router", "routernode"}}
            for node in nodes:
                outgoing = [edge for edge in edges if edge.get("source") == node["id"]]
                if not outgoing:
                    if str(node.get("type", "")).lower() != "end":
                        builder.add_edge(node_name(node["id"]), END)
                    continue
                if str(node.get("type", "")).lower() in conditional_types:
                    path_map = {{(edge.get("conditionLabel") or edge.get("sourceHandle") or "default"): node_name(edge["target"]) for edge in outgoing}}
                    async def _condition(state, _node=node) -> str:
                        return await route_condition(_node, state)
                    builder.add_conditional_edges(node_name(node["id"]), _condition, path_map)
                else:
                    for edge in outgoing:
                        if edge.get("target") in node_by_id:
                            builder.add_edge(node_name(node["id"]), node_name(edge["target"]))
            return builder.compile()


        async def main(query: str) -> dict[str, Any]:
            app = build_graph()
            state: AgentState = {{
                "query": query,
                "messages": [HumanMessage(content=query)],
                "current_output": query,
                "node_results": {{}},
                "metadata": {{}},
                "session_id": None,
                "runtime": make_runtime("exported-run"),
                "artifacts": {{}},
                "trace": [],
            }}
            try:
                result = await app.ainvoke(state)
                print(result.get("current_output", ""))
                return result
            finally:
                await close_mcp_connections()


        if __name__ == "__main__":
            asyncio.run(main(input("Query: ")))
        '''
    ).lstrip()


def _env_example(nodes: list[Any]) -> str:
    lines = []
    for node in nodes:
        if node.node_type.lower() in {"llm", "llmnode", "router", "routernode"}:
            lines.append(f"{_snake(node.label).upper()}_API_KEY=your-key-here")
    return "\n".join(dict.fromkeys(lines)) + ("\n" if lines else "")


def _requirements(nodes: list[Any]) -> str:
    packages = [
        "python-dotenv",
        "httpx",
        "fastmcp",
        "langchain",
        "langgraph",
        "langchain-core",
        "langchain-openai",
        "langchain-google-genai",
        "langchain-anthropic",
        "sqlalchemy",
    ]
    return "\n".join(packages) + "\n"


def _readme(graph: Any) -> str:
    return f"# {graph.name}\n\nGenerated executable LangGraph agent export.\n\n```bash\npip install -r requirements.txt\ncp .env.example .env\npython agent.py\n```\n\nThe original graph is stored in `graph_spec.json`.\n"


def _snake(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", value or "node").strip("_").lower()
    if not name or name[0].isdigit():
        name = f"node_{name}"
    return name
