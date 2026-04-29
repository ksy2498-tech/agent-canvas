import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.codegen.generator import generate_zip
from app.database import get_db
from app.models import MCPServer


router = APIRouter(prefix="/graphs", tags=["download"])


@router.get("/{graph_id}/download")
async def download_graph(graph_id: str, db: AsyncSession = Depends(get_db)):
    graph = await crud.get_graph(db, graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    result = await db.execute(select(MCPServer).where(MCPServer.scope.in_(["global", graph_id])))
    mcp_servers = list(result.scalars().all())
    data = generate_zip(graph, graph.nodes, graph.edges, mcp_servers)
    headers = {"Content-Disposition": f'attachment; filename="{graph.name or graph.id}.zip"'}
    return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers=headers)

