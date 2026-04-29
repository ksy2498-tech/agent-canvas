import io
import json
import re
import textwrap
import zipfile
from typing import Any


def generate_zip(graph: Any, nodes: list[Any], edges: list[Any], mcp_servers: list[Any] | None = None) -> bytes:
    graph_spec = _graph_spec(graph, nodes, edges, mcp_servers or [])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("agent.py", _agent_py(graph_spec))
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
        import inspect
        import json
        import operator
        import os
        from typing import Annotated, Any, TypedDict

        import httpx
        from dotenv import load_dotenv
        from fastmcp import Client
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        from langchain_core.tools import StructuredTool
        from langgraph.graph import END, START, StateGraph

        load_dotenv()

        GRAPH_SPEC = json.loads({graph_json!r})

        SAFE_BUILTINS = {{
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "range": range,
            "round": round,
            "str": str,
            "sum": sum,
            "set": set,
        }}


        class AgentState(TypedDict, total=False):
            query: str
            messages: Annotated[list[Any], operator.add]
            current_output: str
            metadata: dict
            session_id: str | None
            artifact_refs: dict
            trace: Annotated[list[dict], operator.add]


        MCP_SERVERS = {{server["id"]: server for server in GRAPH_SPEC.get("mcpServers", [])}}
        MCP_CONNECTIONS: dict[str, tuple[dict[str, Any], Client]] = {{}}


        def append_trace(node_id: str, label: str, status: str = "ok", **extra: Any) -> dict[str, Any]:
            return {{"trace": [{{"node_id": node_id, "label": label, "status": status, **extra}}]}}


        def get_state_value(state: dict[str, Any], key: str | None) -> Any:
            if not key:
                return None
            value: Any = state
            for part in str(key).split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value


        def tool_value(tool: dict[str, Any], snake_key: str, camel_key: str) -> Any:
            return tool.get(snake_key) or tool.get(camel_key)


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
            elif server.get("transport") == "sse":
                if not config.get("url"):
                    raise ValueError("sse MCP server requires config.url")
                server_config = {{
                    "transport": "sse",
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
                return "gemini-1.5-flash"
            if provider in {{"claude", "anthropic"}}:
                return "claude-3-5-haiku-latest"
            return "gpt-4o-mini"


        async def langchain_mcp_tools(config: dict[str, Any]) -> tuple[list[Any], dict[str, str]]:
            tools = []
            server_by_tool_name = {{}}
            for tool in attached_tools(config):
                server_id = tool_value(tool, "server_id", "serverId")
                name = tool_value(tool, "tool_name", "name")
                if not server_id or not name:
                    continue
                description = tool.get("description") or f"MCP tool {{name}}"
                server_by_tool_name[name] = server_id

                async def _call(payload: dict[str, Any] | None = None, *, _server_id=server_id, _name=name) -> Any:
                    return await call_mcp_tool(_server_id, _name, payload or {{}})

                tools.append(StructuredTool.from_function(coroutine=_call, name=name, description=description))
            return tools, server_by_tool_name


        async def run_llm_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            node_id = node["id"]
            label = node.get("label") or "LLM"
            output_key = config.get("output_key") or config.get("outputKey") or "current_output"
            update_current_output = config.get("update_current_output")
            if update_current_output is None:
                update_current_output = config.get("updateCurrentOutput", True)

            llm = build_chat_model(config)
            lc_tools, server_by_tool_name = await langchain_mcp_tools(config)
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
                name = call.get("name")
                server_id = call.get("server_id") or server_by_tool_name.get(name or "")
                if server_id and name:
                    result = await call_mcp_tool(server_id, name, call.get("args") or {{}})
                    produced_messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", name)))

            output = str(getattr(response, "content", ""))
            updates: AgentState = {{output_key: output, "messages": produced_messages, **append_trace(node_id, label, output_preview=output[:200])}}
            if update_current_output or output_key == "current_output":
                updates["current_output"] = output
            return updates


        async def run_mcp_tool_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            node_id = node["id"]
            label = node.get("label") or "MCP Tool Call"
            tools = attached_tools(config)
            selected = str(get_state_value(state, config.get("toolNameKey") or config.get("tool_name_key")) or "").strip()
            tool = next((item for item in tools if str(tool_value(item, "tool_name", "name") or "").strip() == selected), None) if selected else (tools[0] if tools else None)
            if not tool:
                raise ValueError("No MCP tool selected")
            server_id = tool_value(tool, "server_id", "serverId")
            tool_name = tool_value(tool, "tool_name", "name")
            args_key = config.get("toolArgsKey") or config.get("tool_args_key")
            args = get_state_value(state, args_key) if args_key else None
            if not isinstance(args, dict):
                args = config.get("toolArgs") or config.get("tool_args") or {{}}
            result = await call_mcp_tool(server_id, tool_name, args)
            result_key = config.get("toolResultKey") or config.get("tool_result_key") or "tool_result"
            output = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
            updates: AgentState = {{result_key: result, **append_trace(node_id, label, tool=tool_name, output_preview=output[:200])}}
            update_current_output = config.get("update_current_output")
            if update_current_output is None:
                update_current_output = config.get("updateCurrentOutput", True)
            if update_current_output or result_key == "current_output":
                updates["current_output"] = output
            return updates


        async def run_code_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            namespace: dict[str, Any] = {{"__builtins__": SAFE_BUILTINS}}
            exec(config.get("code", "async def run(state, mcp):\n    return {{}}"), namespace)
            run = namespace.get("run")
            if not callable(run):
                raise ValueError("Code node must define run(state, mcp)")
            mcp = build_mcp_callable_map(config)
            result = run(dict(state), mcp)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, dict):
                raise ValueError("Code node run() must return a dict")
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


        async def run_state_set_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            updates = dict(config.get("values") or config.get("state") or {{}})
            updates.update(append_trace(node["id"], node.get("label") or "State Set"))
            return updates


        async def run_state_get_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            key = config.get("key")
            alias = config.get("output_alias") or config.get("outputAlias") or key
            updates = {{alias: get_state_value(state, key)}} if key else {{}}
            updates.update(append_trace(node["id"], node.get("label") or "State Get"))
            return updates


        async def run_http_node(node: dict[str, Any], state: AgentState) -> AgentState:
            config = node.get("config") or {{}}
            method = config.get("method", "GET")
            url = config.get("url")
            if not url:
                raise ValueError("HTTP node requires url")
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(method, url, json=config.get("json") or None, params=config.get("params") or None, headers=config.get("headers") or None)
            output_key = config.get("outputKey") or config.get("output_key") or "http_result"
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            return {{output_key: payload, "current_output": str(payload), **append_trace(node["id"], node.get("label") or "HTTP Request", status=str(response.status_code))}}


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
            if node_type in {{"stateset", "state_set"}}:
                return await run_state_set_node(node, state)
            if node_type in {{"stateget", "state_get"}}:
                return await run_state_get_node(node, state)
            if node_type in {{"http", "httprequest", "http_request"}}:
                return await run_http_node(node, state)
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
            builder = StateGraph(AgentState)
            nodes = GRAPH_SPEC.get("nodes", [])
            edges = GRAPH_SPEC.get("edges", [])
            node_by_id = {{node["id"]: node for node in nodes}}

            for node in nodes:
                async def _runner(state: AgentState, _node=node) -> AgentState:
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
                    async def _condition(state: AgentState, _node=node) -> str:
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
                "metadata": {{}},
                "session_id": None,
                "artifact_refs": {{}},
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
    ]
    return "\n".join(packages) + "\n"


def _readme(graph: Any) -> str:
    return f"# {graph.name}\n\nGenerated executable LangGraph agent export.\n\n```bash\npip install -r requirements.txt\ncp .env.example .env\npython agent.py\n```\n\nThe original graph is stored in `graph_spec.json`.\n"


def _snake(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", value or "node").strip("_").lower()
    if not name or name[0].isdigit():
        name = f"node_{name}"
    return name
