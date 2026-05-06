from typing import Any

from app.engine.nodes._common import append_trace, read_runtime, runtime_from_config, write_runtime
from app.engine.nodes.state_path import assign_path, path_value, state_value, typed_value
from app.engine.state import AgentState


def build_runtime_set_node(config: dict[str, Any]):
    async def node(state: AgentState, run_config: dict[str, Any] | None = None) -> AgentState:
        runtime = runtime_from_config(run_config)
        section = config.get("section") or "scratch"
        key = config.get("key") or "value"
        value = _source_value(state, runtime, config)
        write_runtime(runtime, section, key, value)
        return append_trace(
            state,
            config.get("_node_id", "runtime_set"),
            config.get("_label", "Runtime Set"),
            section=section,
            key=key,
            source_scope=config.get("source_scope") or config.get("sourceScope") or "literal",
        )

    return node


def build_runtime_get_node(config: dict[str, Any]):
    async def node(state: AgentState, run_config: dict[str, Any] | None = None) -> AgentState:
        runtime = runtime_from_config(run_config)
        section = config.get("section") or "scratch"
        key = config.get("key") or "value"
        target_scope = config.get("target_scope") or config.get("targetScope") or "state"
        output_key = config.get("output_key") or config.get("outputKey") or "current_output"
        value = read_runtime(runtime, section, key)
        updates: AgentState = {}
        if target_scope == "runtime":
            target_section = config.get("target_section") or config.get("targetSection") or "scratch"
            write_runtime(runtime, target_section, output_key, value)
        else:
            assign_path(updates, output_key, value)
        updates.update(
            append_trace(
                state,
                config.get("_node_id", "runtime_get"),
                config.get("_label", "Runtime Get"),
                section=section,
                key=key,
                target_scope=target_scope,
                output_key=output_key,
            )
        )
        return updates

    return node


def _source_value(state: AgentState, runtime: dict[str, Any], config: dict[str, Any]) -> Any:
    source_scope = config.get("source_scope") or config.get("sourceScope") or "literal"
    source_key = config.get("source_key") or config.get("sourceKey")
    if source_scope == "state":
        return state_value(state, source_key)
    if source_scope == "runtime":
        section, _, nested_key = str(source_key or "").partition(".")
        return read_runtime(runtime, section, nested_key or None)
    return typed_value(config.get("value"), config.get("value_type") or config.get("valueType"))
