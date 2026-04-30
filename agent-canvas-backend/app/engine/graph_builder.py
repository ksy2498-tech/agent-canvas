from __future__ import annotations

import inspect
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
from app.engine.nodes._common import make_runtime, runtime_preview
from app.engine.state import AgentState
from app.mcp.registry import resolve_mcp_servers

NodeFn = Callable[..., Awaitable[AgentState]]
PENDING_RUNS: dict[str, dict[str, Any]] = {}


async def build_and_run(
    graph_id: str,
    query: str,
    db: AsyncSession,
    run_id: str | None = None,
    breakpoints: dict[str, Any] | None = None,
    edge_breakpoints: dict[str, Any] | None = None,
    start_node_ids: list[str] | None = None,
    initial_state: AgentState | None = None,
    initial_runtime: dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    run_id = run_id or graph_id
    runtime = initial_runtime or make_runtime(run_id)
    runtime["run_id"] = run_id
    breakpoints = breakpoints or {}
    edge_breakpoints = edge_breakpoints or {}
    graph_record = await crud.get_graph(db, graph_id)
    if graph_record is None:
        yield {"type": "error", "message": "Graph not found", "runId": run_id}
        return

    nodes = list(graph_record.nodes)
    edges = list(graph_record.edges)
    node_by_id = {node.id: node for node in nodes}

    validation_errors = _validate_graph_structure(nodes, edges)
    if validation_errors:
        yield {"type": "error", "message": "Invalid graph: " + "; ".join(validation_errors), "nodeId": None, "runId": run_id}
        return

    try:
        compiled, condition_fns, node_names = await _compile_graph(graph_id, db, nodes, edges, start_node_ids)
    except Exception as exc:
        yield {"type": "error", "message": f"Failed to build graph: {exc}", "nodeId": None, "runId": run_id}
        return

    state: AgentState = initial_state or {
        "query": query,
        "messages": [HumanMessage(content=query)],
        "current_output": query,
        "node_results": {},
        "metadata": {},
        "session_id": None,
        "artifacts": {},
        "trace": [],
    }
    run_config = {"configurable": {"run_id": run_id, "runtime": runtime}}

    try:
        async for chunk in compiled.astream(state, config=run_config):
            for name, update in chunk.items():
                node_id = _id_from_node_name(name, node_by_id)
                node = node_by_id.get(node_id)
                if node:
                    yield {"type": "node_start", "nodeId": node.id, "label": node.label, "runId": run_id}
                if update:
                    state.update(update)
                if node:
                    preview = runtime_preview(runtime)
                    yield {
                        "type": "node_end",
                        "nodeId": node.id,
                        "label": node.label,
                        "status": "ok",
                        "output_preview": str(state.get("current_output", ""))[:200],
                        "node_results": state.get("node_results", {}),
                        "update": update or {},
                        "state": state,
                        "runtime_preview": preview,
                        "runId": run_id,
                    }
                    if node.id in breakpoints:
                        next_node_ids = await _next_node_ids(node.id, state, edges, condition_fns, node_names, run_config)
                        PENDING_RUNS[run_id] = {
                            "graph_id": graph_id,
                            "query": query,
                            "state": state,
                            "runtime": runtime,
                            "next_node_ids": next_node_ids,
                            "breakpoints": breakpoints,
                            "edge_breakpoints": edge_breakpoints,
                            "paused_at": node.id,
                        }
                        yield {
                            "type": "paused",
                            "runId": run_id,
                            "at": node.id,
                            "label": node.label,
                            "state": state,
                            "runtime_preview": preview,
                            "nextNodeIds": next_node_ids,
                            "breakpoint": breakpoints.get(node.id),
                        }
                        return
        PENDING_RUNS.pop(run_id, None)
        yield {
            "type": "done",
            "runId": run_id,
            "output": state.get("current_output", ""),
            "trace": state.get("trace", []),
            "node_results": state.get("node_results", {}),
            "state": state,
            "runtime_preview": runtime_preview(runtime),
        }
    except Exception as exc:
        yield {"type": "error", "message": str(exc), "nodeId": None, "state": state, "runtime_preview": runtime_preview(runtime), "runId": run_id}


async def resume_run(run_id: str, edited_state: dict[str, Any], db: AsyncSession) -> AsyncGenerator[dict[str, Any], None]:
    pending = PENDING_RUNS.get(run_id)
    if not pending:
        yield {"type": "error", "message": "No paused run found", "runId": run_id}
        return
    state = _apply_edited_state(pending.get("state") or {}, edited_state or {})
    runtime = pending.get("runtime") or make_runtime(run_id)
    next_node_ids = list(pending.get("next_node_ids") or [])
    if not next_node_ids:
        PENDING_RUNS.pop(run_id, None)
        yield {
            "type": "done",
            "runId": run_id,
            "output": state.get("current_output", ""),
            "trace": state.get("trace", []),
            "node_results": state.get("node_results", {}),
            "state": state,
            "runtime_preview": runtime_preview(runtime),
        }
        return
    breakpoints = dict(pending.get("breakpoints") or {})
    breakpoints.pop(pending.get("paused_at"), None)
    async for event in build_and_run(
        graph_id=pending["graph_id"],
        query=pending.get("query") or state.get("query") or "",
        db=db,
        run_id=run_id,
        breakpoints=breakpoints,
        edge_breakpoints=pending.get("edge_breakpoints") or {},
        start_node_ids=next_node_ids,
        initial_state=state,
        initial_runtime=runtime,
    ):
        yield event


def _apply_edited_state(existing: dict[str, Any], edited: dict[str, Any]) -> AgentState:
    state = dict(existing)
    for key, value in edited.items():
        if key == "messages":
            continue
        state[key] = value
    return state


async def _compile_graph(
    graph_id: str,
    db: AsyncSession,
    nodes: list[Any],
    edges: list[Any],
    start_node_ids: list[str] | None,
):
    attached = []
    for node in nodes:
        config = node.config or {}
        attached.extend(config.get("attached_mcp_tools") or config.get("attachedTools") or [])
    mcp_servers = await resolve_mcp_servers(db, graph_id, attached)

    builder = StateGraph(AgentState)
    condition_fns: dict[str, Callable[..., Awaitable[str]]] = {}
    node_names = {node.id: _node_name(node.id) for node in nodes}

    async def make_wrapped(node, fn: NodeFn) -> NodeFn:
        async def wrapped(state: AgentState, config: dict[str, Any] | None = None) -> AgentState:
            return await _run_node_with_events(node, fn, state, config)

        return wrapped

    for node in nodes:
        fn_or_tuple = _build_node(node, nodes, mcp_servers)
        if isinstance(fn_or_tuple, tuple):
            node_fn, condition_fn = fn_or_tuple
            condition_fns[node.id] = condition_fn
        else:
            node_fn = fn_or_tuple
        builder.add_node(node_names[node.id], await make_wrapped(node, node_fn))

    resolved_start_ids = start_node_ids or _default_start_node_ids(nodes)
    for node_id in resolved_start_ids:
        if node_id in node_names:
            builder.add_edge(START, node_names[node_id])

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

    return builder.compile(), condition_fns, node_names


async def _next_node_ids(
    node_id: str,
    state: AgentState,
    edges: list[Any],
    condition_fns: dict[str, Callable[..., Awaitable[str]]],
    node_names: dict[str, str],
    runtime_config: dict[str, Any] | None = None,
) -> list[str]:
    outgoing = [edge for edge in edges if edge.source_node_id == node_id]
    if not outgoing:
        return []
    if node_id not in condition_fns:
        return [edge.target_node_id for edge in outgoing]
    selected = await _call_node_fn(condition_fns[node_id], state, runtime_config)
    for edge in outgoing:
        label = edge.condition_label or edge.source_handle or "default"
        if label == selected and edge.target_node_id in node_names:
            return [edge.target_node_id]
    for edge in outgoing:
        label = edge.condition_label or edge.source_handle or "default"
        if label == "default" and edge.target_node_id in node_names:
            return [edge.target_node_id]
    return []


async def _run_node_with_events(node, fn: NodeFn, state: AgentState, config: dict[str, Any] | None = None) -> AgentState:
    if node.node_type.lower() in {"start", "end"}:
        return {"trace": [{"node_id": node.id, "label": node.label, "status": "ok"}]}
    return await _call_node_fn(fn, state, config)


async def _call_node_fn(fn: Callable[..., Awaitable[Any]], state: AgentState, config: dict[str, Any] | None = None) -> Any:
    params = inspect.signature(fn).parameters
    if len(params) >= 2:
        return await fn(state, config)
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


def _default_start_node_ids(nodes: list[Any]) -> list[str]:
    start_nodes = [node for node in nodes if node.node_type.lower() == "start"]
    first_node = start_nodes[0] if start_nodes else (nodes[0] if nodes else None)
    return [first_node.id] if first_node else []


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
