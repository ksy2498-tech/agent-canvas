from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from app.engine.state import AgentState
from app.mcp.client import mcp_client


SAFE_BUILTINS = {
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
}


def append_trace(state: AgentState, node_id: str, label: str, status: str = "ok", **extra: Any) -> AgentState:
    trace = [{"node_id": node_id, "label": label, "status": status, **extra}]
    return {"trace": trace}


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def build_mcp_callable_map(attached_tools: list[dict[str, Any]], mcp_servers: dict[str, Any]) -> dict[str, dict[str, Callable]]:
    result: dict[str, dict[str, Callable]] = {}
    for tool in attached_tools:
        server_id = tool.get("server_id")
        tool_name = tool.get("tool_name")
        if not server_id or not tool_name or server_id not in mcp_servers:
            continue
        server_name = getattr(mcp_servers[server_id], "name", server_id)

        async def _call(args: dict[str, Any] | None = None, *, _server_id=server_id, _tool_name=tool_name) -> Any:
            return await mcp_client.call_tool(_server_id, _tool_name, args or {})

        result.setdefault(server_name, {})[tool_name] = _call
    return result


def run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.create_task(coro)

