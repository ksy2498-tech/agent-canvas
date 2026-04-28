from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import models, schemas


async def create_graph(db: AsyncSession, payload: schemas.GraphCreate) -> models.Graph:
    graph = models.Graph(name=payload.name, description=payload.description)
    db.add(graph)
    await db.flush()
    await replace_graph_children(db, graph, payload.nodes, payload.edges)
    await db.commit()
    return await get_graph(db, graph.id)  # type: ignore[return-value]


async def list_graphs(db: AsyncSession) -> list[models.Graph]:
    result = await db.execute(
        select(models.Graph)
        .options(selectinload(models.Graph.nodes), selectinload(models.Graph.edges))
        .order_by(models.Graph.updated_at.desc())
    )
    return list(result.scalars().unique().all())


async def get_graph(db: AsyncSession, graph_id: str) -> models.Graph | None:
    result = await db.execute(
        select(models.Graph)
        .where(models.Graph.id == graph_id)
        .options(selectinload(models.Graph.nodes), selectinload(models.Graph.edges))
    )
    return result.scalars().unique().one_or_none()


async def update_graph(db: AsyncSession, graph_id: str, payload: schemas.GraphUpdate) -> models.Graph | None:
    graph = await get_graph(db, graph_id)
    if graph is None:
        return None
    graph.name = payload.name
    graph.description = payload.description
    await db.execute(delete(models.GraphEdge).where(models.GraphEdge.graph_id == graph_id))
    await db.execute(delete(models.GraphNode).where(models.GraphNode.graph_id == graph_id))
    await db.flush()
    await replace_graph_children(db, graph, payload.nodes, payload.edges)
    await db.commit()
    return await get_graph(db, graph_id)


async def replace_graph_children(
    db: AsyncSession,
    graph: models.Graph,
    nodes: list[schemas.GraphNodeBase],
    edges: list[schemas.GraphEdgeBase],
) -> None:
    for node in nodes:
        db.add(
            models.GraphNode(
                id=node.id or models.new_uuid(),
                graph_id=graph.id,
                node_type=node.node_type,
                label=node.label,
                position_x=node.position_x,
                position_y=node.position_y,
                config=node.config,
            )
        )
    await db.flush()
    for edge in edges:
        db.add(
            models.GraphEdge(
                id=edge.id or models.new_uuid(),
                graph_id=graph.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                source_handle=edge.source_handle,
                target_handle=edge.target_handle,
                condition_label=edge.condition_label,
                has_breakpoint=False,
            )
        )


async def delete_graph(db: AsyncSession, graph_id: str) -> bool:
    graph = await get_graph(db, graph_id)
    if graph is None:
        return False
    await db.delete(graph)
    await db.commit()
    return True


async def list_mcp_servers(db: AsyncSession, scope: str | None = None) -> list[models.MCPServer]:
    stmt = select(models.MCPServer).order_by(models.MCPServer.created_at.desc())
    if scope:
        stmt = stmt.where(models.MCPServer.scope == scope)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_mcp_server(db: AsyncSession, server_id: str) -> models.MCPServer | None:
    return await db.get(models.MCPServer, server_id)


async def create_mcp_server(db: AsyncSession, payload: schemas.MCPServerCreate) -> models.MCPServer:
    server = models.MCPServer(**payload.model_dump())
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def update_mcp_server(
    db: AsyncSession, server_id: str, payload: schemas.MCPServerUpdate
) -> models.MCPServer | None:
    server = await get_mcp_server(db, server_id)
    if server is None:
        return None
    for key, value in payload.model_dump().items():
        setattr(server, key, value)
    await db.commit()
    await db.refresh(server)
    return server


async def delete_mcp_server(db: AsyncSession, server_id: str) -> bool:
    server = await get_mcp_server(db, server_id)
    if server is None:
        return False
    await db.delete(server)
    await db.commit()
    return True
