from fastapi import Header


DEFAULT_USER_ID = "local-user"


async def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    # LOGIN TODO: Replace this placeholder with real auth later.
    # For JWT/session auth, validate the token here and return the authenticated
    # user's stable database id. Keep routers depending on this function so
    # graph/MCP ownership filtering continues to work without route changes.
    user_id = (x_user_id or DEFAULT_USER_ID).strip()
    return user_id or DEFAULT_USER_ID
