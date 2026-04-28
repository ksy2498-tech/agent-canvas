from typing import Any

from langchain_core.messages import HumanMessage

from app.engine.llm_provider import build_chat_model
from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_router_node(config: dict[str, Any], mcp_servers: dict[str, Any]):
    async def node_fn(state: AgentState) -> AgentState:
        return append_trace(state, config.get("_node_id", "router"), config.get("_label", "Router"))

    async def condition_fn(state: AgentState) -> str:
        routes = config.get("routes") or config.get("conditions") or []
        text = state.get("current_output") or state.get("query", "")
        mode = config.get("mode") or config.get("routingMode") or "keyword-match"
        if mode == "llm-based":
            llm = build_chat_model(config, temperature=0)
            labels = [route.get("label") for route in routes]
            response = await llm.ainvoke(
                [HumanMessage(content=f"Pick exactly one route label from {labels} for this text:\n{text}")]
            )
            return str(response.content).strip()
        lower = text.lower()
        for route in routes:
            label = route.get("label") or route.get("condition_label")
            keywords = route.get("keywords", [])
            if any(str(keyword).lower() in lower for keyword in keywords):
                return label
        return config.get("default_route") or (routes[0].get("label") if routes else "default")

    return node_fn, condition_fn
