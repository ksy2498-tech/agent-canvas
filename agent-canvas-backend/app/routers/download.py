import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.codegen.generator import generate_zip
from app.database import get_db


router = APIRouter(prefix="/graphs", tags=["download"])


@router.get("/{graph_id}/download")
async def download_graph(graph_id: str, db: AsyncSession = Depends(get_db)):
    graph = await crud.get_graph(db, graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    data = generate_zip(graph, graph.nodes, graph.edges)
    headers = {"Content-Disposition": f'attachment; filename="{graph.name or graph.id}.zip"'}
    return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers=headers)

