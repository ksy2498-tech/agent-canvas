from typing import Annotated, Any, Optional, TypedDict
import operator

from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    query: str
    messages: Annotated[list[BaseMessage], operator.add]
    nlp_result: Optional[dict]
    current_output: str
    metadata: dict
    session_id: Optional[str]
    artifact_refs: dict
    db_result: Optional[Any]
    http_result: Optional[Any]
    trace: Annotated[list[dict], operator.add]
