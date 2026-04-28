from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MCPServer


async def resolve_mcp_servers(db: AsyncSession, graph_id: str, attached_tools: list[dict]) -> dict[str, MCPServer]:
    server_ids = {tool.get("server_id") or tool.get("serverId") for tool in attached_tools if tool.get("server_id") or tool.get("serverId")}
    if not server_ids:
        return {}
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id.in_(server_ids),
            or_(MCPServer.scope == "global", MCPServer.scope == graph_id),
        )
    )
    return {server.id: server for server in result.scalars().all()}
