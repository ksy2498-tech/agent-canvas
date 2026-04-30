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


def make_runtime(run_id: str | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "session": {},
        "tool_results": {},
        "nlp": {},
        "artifacts": {},
        "scratch": {},
    }


def runtime_from_config(config: dict[str, Any] | None) -> dict[str, Any]:
    configurable = (config or {}).get("configurable") or {}
    runtime = configurable.get("runtime")
    if runtime is None:
        runtime = make_runtime(configurable.get("run_id"))
        configurable["runtime"] = runtime
        if config is not None:
            config["configurable"] = configurable
    return runtime


def runtime_preview(runtime: dict[str, Any] | None) -> dict[str, Any]:
    runtime = runtime or {}
    return {
        "session_keys": sorted((runtime.get("session") or {}).keys()),
        "tool_result_keys": sorted((runtime.get("tool_results") or {}).keys()),
        "nlp_keys": sorted((runtime.get("nlp") or {}).keys()),
        "artifact_keys": sorted((runtime.get("artifacts") or {}).keys()),
        "scratch_keys": sorted((runtime.get("scratch") or {}).keys()),
    }


def write_runtime(runtime: dict[str, Any], section: str, key: str, value: Any) -> None:
    runtime.setdefault(section, {})[key] = value


def read_runtime(runtime: dict[str, Any], section: str, key: str | None = None) -> Any:
    section_value = runtime.get(section, {})
    if key is None:
        return section_value
    return _path_value(section_value, key)


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
        server_id = tool.get("server_id") or tool.get("serverId")
        tool_name = tool.get("tool_name") or tool.get("name")
        if not server_id or not tool_name or server_id not in mcp_servers:
            continue
        server = mcp_servers[server_id]
        server_name = getattr(server, "name", server_id)

        async def _call(args: dict[str, Any] | None = None, *, _server_id=server_id, _server=server, _tool_name=tool_name) -> Any:
            await mcp_client.connect(_server)
            return await mcp_client.call_tool(_server_id, _tool_name, args or {})

        result.setdefault(server_name, {})[tool_name] = _call
    return result


def run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.create_task(coro)


def _path_value(value: Any, key: str | None) -> Any:
    if not key:
        return value
    for part in str(key).split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return value
