from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.database import get_db
from app.mcp.client import mcp_client


router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers", response_model=list[schemas.MCPServerRead])
async def list_servers(scope: str | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    return await crud.list_mcp_servers(db, scope)


@router.post("/servers", response_model=schemas.MCPServerRead, status_code=status.HTTP_201_CREATED)
async def create_server(payload: schemas.MCPServerCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_mcp_server(db, payload)


@router.put("/servers/{server_id}", response_model=schemas.MCPServerRead)
async def update_server(server_id: str, payload: schemas.MCPServerUpdate, db: AsyncSession = Depends(get_db)):
    server = await crud.update_mcp_server(db, server_id, payload)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await mcp_client.disconnect(server_id)
    return server


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await crud.delete_mcp_server(db, server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await mcp_client.disconnect(server_id)
    return None


@router.post("/test")
async def test_server(payload: schemas.MCPTestRequest, db: AsyncSession = Depends(get_db)):
    server = await crud.get_mcp_server(db, payload.id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    try:
        await mcp_client.connect(server)
        tools = await mcp_client.list_tools(server.id)
        return {"status": "ok", "tools": tools}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "tools": []}


@router.get("/servers/{server_id}/tools")
async def server_tools(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await crud.get_mcp_server(db, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await mcp_client.connect(server)
    return {"tools": await mcp_client.list_tools(server.id)}

