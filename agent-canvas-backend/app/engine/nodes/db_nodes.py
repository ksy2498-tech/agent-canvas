from typing import Any

from sqlalchemy import create_engine, text

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_db_query_node(config: dict[str, Any], graph_nodes: list[Any]):
    async def node(state: AgentState) -> AgentState:
        alias = config.get("connection_alias")
        connection = None
        for graph_node in graph_nodes:
            node_config = getattr(graph_node, "config", {}) or {}
            if graph_node.node_type in {"DBConnection", "db_connection"} and node_config.get("alias") == alias:
                connection = node_config
                break
        if connection is None:
            connection = config
        url = connection.get("url") or connection.get("database_url")
        if not url:
            raise ValueError("DB query node requires connection url/database_url")
        engine = create_engine(url.replace("+aiosqlite", ""), future=True)
        with engine.begin() as conn:
            result = conn.execute(text(config.get("query", "")), config.get("params", {}))
            rows = [dict(row._mapping) for row in result] if result.returns_rows else []
        output_key = config.get("output_key", "db_result")
        return {
            output_key: rows,
            "db_result": rows,
            **append_trace(state, config.get("_node_id", "db_query"), config.get("_label", "DB Query"), row_count=len(rows)),
        }

    return node

