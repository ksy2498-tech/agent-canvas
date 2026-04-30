from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphNodeBase(BaseModel):
    id: str | None = None
    node_type: str
    label: str
    position_x: float = 0
    position_y: float = 0
    config: dict[str, Any] = Field(default_factory=dict)


class GraphNodeRead(GraphNodeBase):
    id: str
    graph_id: str
    model_config = ConfigDict(from_attributes=True)


class GraphEdgeBase(BaseModel):
    id: str | None = None
    source_node_id: str
    target_node_id: str
    source_handle: str = ""
    target_handle: str = ""
    condition_label: str | None = None


class GraphEdgeRead(GraphEdgeBase):
    id: str
    graph_id: str
    model_config = ConfigDict(from_attributes=True)


class GraphCreate(BaseModel):
    name: str
    description: str | None = None
    nodes: list[GraphNodeBase] = Field(default_factory=list)
    edges: list[GraphEdgeBase] = Field(default_factory=list)


class GraphUpdate(GraphCreate):
    pass


class GraphRead(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    nodes: list[GraphNodeRead] = Field(default_factory=list)
    edges: list[GraphEdgeRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class RunRequest(BaseModel):
    query: str
    breakpoints: dict[str, Any] = Field(default_factory=dict)
    edgeBreakpoints: dict[str, Any] = Field(default_factory=dict)


class ResumeRequest(BaseModel):
    runId: str
    editedState: dict[str, Any] = Field(default_factory=dict)


class MCPServerCreate(BaseModel):
    name: str
    scope: str = "global"
    transport: Literal["stdio", "sse", "streamable-http"]
    config: dict[str, Any] = Field(default_factory=dict)


class MCPServerUpdate(MCPServerCreate):
    pass


class MCPServerRead(MCPServerCreate):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MCPTestRequest(BaseModel):
    id: str
