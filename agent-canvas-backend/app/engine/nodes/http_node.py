import re
from typing import Any

import httpx

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def _interpolate(value: Any, state: AgentState) -> Any:
    if isinstance(value, str):
        def repl(match):
            key = match.group(1)
            cursor: Any = state
            for part in key.split("."):
                cursor = cursor.get(part) if isinstance(cursor, dict) else getattr(cursor, part, "")
            return str(cursor)

        return re.sub(r"{state\.([^}]+)}", repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, state) for v in value]
    return value


def build_http_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        async with httpx.AsyncClient(timeout=config.get("timeout", 30)) as client:
            response = await client.request(
                config.get("method", "GET"),
                _interpolate(config.get("url", ""), state),
                headers=_interpolate(config.get("headers", {}), state),
                params=_interpolate(config.get("params", {}), state),
                json=_interpolate(config.get("json"), state) if "json" in config else None,
                data=_interpolate(config.get("body"), state) if "body" in config else None,
            )
        try:
            body = response.json()
        except ValueError:
            body = response.text
        result = {"status_code": response.status_code, "headers": dict(response.headers), "body": body}
        output_key = config.get("output_key", "http_result")
        return {
            output_key: result,
            "http_result": result,
            **append_trace(state, config.get("_node_id", "http"), config.get("_label", "HTTP"), status_code=response.status_code),
        }

    return node

