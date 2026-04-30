from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.engine.nodes import (
    build_artifact_load_node,
    build_artifact_store_node,
    build_code_node,
    build_condition_node,
    build_db_query_node,
    build_http_node,
    build_input_transform_node,
    build_llm_node,
    build_mcp_tool_node,
    build_nlp_node,
    build_output_format_node,
    build_router_node,
    build_session_load_node,
    build_session_save_node,
    build_state_get_node,
    build_state_set_node,
)
from app.engine.state import AgentState
from app.mcp.registry import resolve_mcp_servers

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


async def build_and_run(
    graph_id: str,
    query: str,
    db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    graph_record = await crud.get_graph(db, graph_id)
    if graph_record is None:
        yield {"type": "error", "message": "Graph not found"}
        return

    nodes = list(graph_record.nodes)
    edges = list(graph_record.edges)
    node_by_id = {node.id: node for node in nodes}

    validation_errors = _validate_graph_structure(nodes, edges)
    if validation_errors:
        yield {"type": "error", "message": "Invalid graph: " + "; ".join(validation_errors), "nodeId": None}
        return

    attached = []
    for node in nodes:
        config = node.config or {}
        attached.extend(config.get("attached_mcp_tools") or config.get("attachedTools") or [])
    try:
        mcp_servers = await resolve_mcp_servers(db, graph_id, attached)

        builder = StateGraph(AgentState)
        condition_fns: dict[str, Callable[[AgentState], Awaitable[str]]] = {}
        node_names = {node.id: _node_name(node.id) for node in nodes}

        async def make_wrapped(node, fn: NodeFn) -> NodeFn:
            async def wrapped(state: AgentState) -> AgentState:
                return await _run_node_with_events(node, fn, state)

            return wrapped

        for node in nodes:
            fn_or_tuple = _build_node(node, nodes, mcp_servers)
            if isinstance(fn_or_tuple, tuple):
                node_fn, condition_fn = fn_or_tuple
                condition_fns[node.id] = condition_fn
            else:
                node_fn = fn_or_tuple
            builder.add_node(node_names[node.id], await make_wrapped(node, node_fn))

        start_nodes = [node for node in nodes if node.node_type.lower() == "start"]
        first_node = start_nodes[0] if start_nodes else (nodes[0] if nodes else None)
        if first_node is None:
            yield {"type": "done", "output": query, "trace": [], "state": {"query": query}}
            return
        builder.add_edge(START, node_names[first_node.id])

        for node in nodes:
            outgoing = [edge for edge in edges if edge.source_node_id == node.id]
            if not outgoing:
                if node.node_type.lower() != "end":
                    builder.add_edge(node_names[node.id], END)
                continue
            if node.id in condition_fns:
                path_map = {
                    edge.condition_label or edge.source_handle or "default": node_names[edge.target_node_id]
                    for edge in outgoing
                }
                builder.add_conditional_edges(node_names[node.id], condition_fns[node.id], path_map)
            else:
                for edge in outgoing:
                    builder.add_edge(node_names[node.id], node_names[edge.target_node_id])

        compiled = builder.compile()
    except Exception as exc:
        yield {"type": "error", "message": f"Failed to build graph: {exc}", "nodeId": None}
        return
    state: AgentState = {
        "query": query,
        "messages": [HumanMessage(content=query)],
        "current_output": query,
        "node_results": {},
        "metadata": {},
        "session_id": None,
        "artifact_refs": {},
        "trace": [],
    }

    try:
        async for chunk in compiled.astream(state):
            for name, update in chunk.items():
                node_id = _id_from_node_name(name, node_by_id)
                node = node_by_id.get(node_id)
                if node:
                    yield {"type": "node_start", "nodeId": node.id, "label": node.label}
                if update:
                    state.update(update)
                if node:
                    yield {
                        "type": "node_end",
                        "nodeId": node.id,
                        "label": node.label,
                        "status": "ok",
                        "output_preview": str(state.get("current_output", ""))[:200],
                        "node_results": state.get("node_results", {}),
                        "update": update or {},
                        "state": state,
                    }
        yield {
            "type": "done",
            "output": state.get("current_output", ""),
            "trace": state.get("trace", []),
            "node_results": state.get("node_results", {}),
            "state": state,
        }
    except Exception as exc:
        yield {"type": "error", "message": str(exc), "nodeId": None, "state": state}


async def _run_node_with_events(node, fn: NodeFn, state: AgentState) -> AgentState:
    if node.node_type.lower() in {"start", "end"}:
        return {"trace": [{"node_id": node.id, "label": node.label, "status": "ok"}]}
    return await fn(state)


def _build_node(node, graph_nodes, mcp_servers):
    config = dict(node.config or {})
    config["_node_id"] = node.id
    config["_label"] = node.label
    node_type = node.node_type.lower()
    if node_type in {"start", "end"}:
        async def passthrough(state: AgentState) -> AgentState:
            return {}
        return passthrough
    if node_type in {"llm", "llmnode"}:
        return build_llm_node(config, mcp_servers)
    if node_type in {"mcptool", "mcp_tool", "mcptoolcall", "mcp_tool_call"}:
        return build_mcp_tool_node(config, mcp_servers)
    if node_type in {"code", "codenode"}:
        return build_code_node(config, mcp_servers)
    if node_type in {"router", "routernode"}:
        return build_router_node(config, mcp_servers)
    if node_type in {"condition", "conditionnode"}:
        return build_condition_node(config)
    if node_type in {"sessionload", "session_load"}:
        return build_session_load_node(config)
    if node_type in {"sessionsave", "session_save"}:
        return build_session_save_node(config)
    if node_type in {"stateset", "state_set"}:
        return build_state_set_node(config)
    if node_type in {"stateget", "state_get"}:
        return build_state_get_node(config)
    if node_type in {"dbquery", "db_query"}:
        return build_db_query_node(config, graph_nodes)
    if node_type in {"artifactstore", "artifact_store"}:
        return build_artifact_store_node(config)
    if node_type in {"artifactload", "artifact_load"}:
        return build_artifact_load_node(config)
    if node_type in {"http", "http_request"}:
        return build_http_node(config)
    if node_type in {"inputtransform", "input_transform"}:
        return build_input_transform_node(config, mcp_servers)
    if node_type in {"outputformat", "output_format"}:
        return build_output_format_node(config)
    if node_type in {"nlp", "nlpnode"}:
        return build_nlp_node(config)
    async def unknown(state: AgentState) -> AgentState:
        return {"trace": [{"node_id": node.id, "label": node.label, "status": "skipped", "reason": "unknown node type"}]}
    return unknown


def _validate_graph_structure(nodes: list[Any], edges: list[Any]) -> list[str]:
    node_ids = {node.id for node in nodes}
    node_by_id = {node.id: node for node in nodes}
    errors = []
    for edge in edges:
        if edge.source_node_id not in node_ids:
            errors.append(f"edge {edge.id} source node {edge.source_node_id} does not exist")
        if edge.target_node_id not in node_ids:
            errors.append(f"edge {edge.id} target node {edge.target_node_id} does not exist")
        source = node_by_id.get(edge.source_node_id)
        target = node_by_id.get(edge.target_node_id)
        if target and target.node_type.lower() == "start":
            errors.append(f"edge {edge.id} cannot target Start node {target.id}")
        if source and source.node_type.lower() == "end":
            errors.append(f"edge {edge.id} cannot start from End node {source.id}")
    return errors


def _node_name(node_id: str) -> str:
    return f"node_{node_id.replace('-', '_')}"


def _id_from_node_name(name: str, node_by_id: dict[str, Any]) -> str:
    if name.startswith("node_"):
        suffix = name.removeprefix("node_")
        for node_id in node_by_id:
            if suffix == node_id.replace("-", "_"):
                return node_id
    return name
