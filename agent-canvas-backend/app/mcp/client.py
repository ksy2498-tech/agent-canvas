from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastmcp import Client
from langchain_core.tools import BaseTool, StructuredTool

from app.models import MCPServer


@dataclass
class _Connection:
    server: MCPServer
    client: Client
    tools_cache: list[dict[str, Any]] | None = None
    entered: bool = False


class MCPClient:
    def __init__(self) -> None:
        self._connections: dict[str, _Connection] = {}

    async def connect(self, server: MCPServer) -> None:
        existing = self._connections.get(server.id)
        if existing and existing.entered:
            return

        client = Client(self._fastmcp_config(server))
        await client.__aenter__()
        self._connections[server.id] = _Connection(server=server, client=client, entered=True)

    async def disconnect(self, server_id: str) -> None:
        conn = self._connections.pop(server_id, None)
        if conn and conn.entered:
            await conn.client.__aexit__(None, None, None)

    async def list_tools(self, server_id: str) -> list[dict[str, Any]]:
        conn = self._require(server_id)
        if conn.tools_cache is not None:
            return conn.tools_cache
        tools = await conn.client.list_tools()
        conn.tools_cache = [self._tool_to_dict(tool) for tool in tools]
        return conn.tools_cache

    async def call_tool(self, server_id: str, tool_name: str, args: dict[str, Any]) -> Any:
        conn = self._require(server_id)
        result = await conn.client.call_tool(tool_name, args or {})
        return self._serialize(result)

    async def as_langchain_tools(self, server_id: str, allowed_tool_names: set[str] | None = None) -> list[BaseTool]:
        tools = []
        for tool_def in await self.list_tools(server_id):
            name = tool_def.get("name", "mcp_tool")
            if allowed_tool_names and name not in allowed_tool_names:
                continue
            description = _tool_description(tool_def)

            async def _call(payload: dict[str, Any] | None = None, *, _name=name) -> Any:
                return await self.call_tool(server_id, _name, payload or {})

            tools.append(StructuredTool.from_function(coroutine=_call, name=name, description=description))
        return tools

    def _require(self, server_id: str) -> _Connection:
        conn = self._connections.get(server_id)
        if conn is None or not conn.entered:
            raise RuntimeError(f"MCP server {server_id} is not connected")
        return conn

    def _fastmcp_config(self, server: MCPServer) -> dict[str, Any]:
        name = server.name or server.id
        if server.transport == "stdio":
            command = server.config.get("command")
            if not command:
                raise ValueError("stdio MCP server requires config.command")
            server_config = {
                "transport": "stdio",
                "command": command,
                "args": server.config.get("args", []),
            }
            if server.config.get("env"):
                server_config["env"] = server.config["env"]
            if server.config.get("cwd"):
                server_config["cwd"] = server.config["cwd"]
        elif server.transport == "sse":
            url = server.config.get("url")
            if not url:
                raise ValueError("sse MCP server requires config.url")
            server_config = {
                "transport": "sse",
                "url": url,
                "headers": server.config.get("headers", {}),
            }
        else:
            raise ValueError(f"Unsupported MCP transport: {server.transport}")
        return {"mcpServers": {name: server_config}}

    def _tool_to_dict(self, tool: Any) -> dict[str, Any]:
        if isinstance(tool, dict):
            return tool
        if hasattr(tool, "model_dump"):
            data = tool.model_dump()
        elif hasattr(tool, "dict"):
            data = tool.dict()
        else:
            data = {
                "name": getattr(tool, "name", "mcp_tool"),
                "description": getattr(tool, "description", ""),
                "inputSchema": getattr(tool, "inputSchema", None),
            }
        return self._serialize(data)

    def _serialize(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return self._serialize(value.model_dump())
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, tuple):
            return [self._serialize(item) for item in value]
        if hasattr(value, "data"):
            return self._serialize(value.data)
        if hasattr(value, "content"):
            return self._serialize(value.content)
        if hasattr(value, "text"):
            return value.text
        return value


def _tool_description(tool_def: dict[str, Any]) -> str:
    description = tool_def.get("description") or f"MCP tool {tool_def.get('name', 'mcp_tool')}"
    schema = tool_def.get("inputSchema") or tool_def.get("input_schema") or tool_def.get("parameters")
    if schema:
        return f"{description}\nInput schema: {json.dumps(schema, ensure_ascii=False)}"
    return description


mcp_client = MCPClient()
