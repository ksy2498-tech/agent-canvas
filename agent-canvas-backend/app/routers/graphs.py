from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.auth import get_current_user_id
from app.database import get_db


router = APIRouter(prefix="/graphs", tags=["graphs"])


@router.post("", response_model=schemas.GraphRead, status_code=status.HTTP_201_CREATED)
async def create_graph(
    payload: schemas.GraphCreate,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    return await crud.create_graph(db, payload, owner_id)


@router.get("", response_model=list[schemas.GraphRead])
async def list_graphs(db: AsyncSession = Depends(get_db), owner_id: str = Depends(get_current_user_id)):
    return await crud.list_graphs(db, owner_id)


@router.get("/{graph_id}", response_model=schemas.GraphRead)
async def get_graph(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    graph = await crud.get_graph(db, graph_id, owner_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph


@router.put("/{graph_id}", response_model=schemas.GraphRead)
async def update_graph(
    graph_id: str,
    payload: schemas.GraphUpdate,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    graph = await crud.update_graph(db, graph_id, payload, owner_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph


@router.delete("/{graph_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    deleted = await crud.delete_graph(db, graph_id, owner_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Graph not found")
    return None
