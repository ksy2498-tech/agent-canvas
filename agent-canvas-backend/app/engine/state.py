from typing import Annotated, Any, Optional, TypedDict
import operator

from langchain_core.messages import BaseMessage


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    merged = dict(left or {})
    for key, value in (right or {}).items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


class AgentState(TypedDict, total=False):
    query: str
    messages: Annotated[list[BaseMessage], operator.add]
    nlp_result: Optional[dict]
    current_output: str
    current_artifact_id: Optional[str]
    loaded_session: Annotated[dict, merge_dicts]
    node_results: Annotated[dict, merge_dicts]
    metadata: Annotated[dict, merge_dicts]
    session_id: Optional[str]
    artifact_refs: Annotated[dict, merge_dicts]
    latest_artifacts: Annotated[dict, merge_dicts]
    db_result: Optional[Any]
    http_result: Optional[Any]
    trace: Annotated[list[dict], operator.add]
