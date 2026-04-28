# Agent Canvas Backend

FastAPI backend for building, running, exporting, and managing LangGraph workflows.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` as needed:

```env
DATABASE_URL=sqlite+aiosqlite:///./agent_canvas.db
OPENAI_API_KEY=your-key-here
```

## Run

```bash
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

## Endpoints

- `POST /graphs`
- `GET /graphs`
- `GET /graphs/{id}`
- `PUT /graphs/{id}`
- `DELETE /graphs/{id}`
- `POST /graphs/{id}/run`
- `GET /graphs/{id}/download`
- `GET /mcp/servers?scope=global`
- `POST /mcp/servers`
- `PUT /mcp/servers/{id}`
- `DELETE /mcp/servers/{id}`
- `POST /mcp/test`
- `GET /mcp/servers/{id}/tools`

## Notes

The service creates database tables on startup. Run streams are returned as SSE events using `sse-starlette`. MCP connections are managed with `fastmcp`.
