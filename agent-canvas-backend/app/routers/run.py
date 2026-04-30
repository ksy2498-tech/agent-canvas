import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.database import get_db
from app.engine.graph_builder import build_and_run, resume_run


router = APIRouter(tags=["run"])


async def _event_stream(generator: AsyncGenerator[dict, None]) -> AsyncGenerator[dict, None]:
    async for event in generator:
        yield {"event": event.get("type", "message"), "data": json.dumps(event, default=str)}


@router.post("/graphs/{graph_id}/run")
async def run_graph(graph_id: str, payload: schemas.RunRequest, db: AsyncSession = Depends(get_db)):
    graph = await crud.get_graph(db, graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    generator = build_and_run(
        graph_id=graph_id,
        query=payload.query,
        db=db,
        run_id=getattr(payload, "runId", None) or None,
        breakpoints=payload.breakpoints,
        edge_breakpoints=payload.edgeBreakpoints,
    )
    return EventSourceResponse(_event_stream(generator))


@router.post("/graphs/{graph_id}/resume")
async def resume_graph(graph_id: str, payload: schemas.ResumeRequest, db: AsyncSession = Depends(get_db)):
    graph = await crud.get_graph(db, graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    generator = resume_run(
        run_id=payload.runId,
        edited_state=payload.editedState,
        db=db,
    )
    return EventSourceResponse(_event_stream(generator))
