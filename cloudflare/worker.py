"""Cloudflare Workers entrypoint for the VERUM application.

The migration intentionally exposes only readiness and Telegram webhook plumbing
until the PostgreSQL schema has been imported into D1.  Keeping the webhook off
prevents a partially migrated Worker from receiving production updates.
"""

from fastapi import FastAPI, Request
from fastapi.responses import Response
from workers import asgi


app = FastAPI(title="VERUM Competitions (Cloudflare)")
Default = asgi.entrypoint(app)


@app.get("/api/health")
async def health(request: Request) -> dict:
    result = await request.scope["env"].DB.prepare("SELECT 1 AS ok").first()
    return {"status": "ok", "database": "d1", "query": int(result.ok)}


@app.get("/{path:path}")
async def frontend(path: str, request: Request) -> Response:
    asset_path = path or "index.html"
    response = await request.scope["env"].ASSETS.fetch(
        f"https://assets.local/{asset_path}"
    )
    return Response(
        content=await response.bytes(),
        status_code=response.status,
        headers=dict(response.headers),
    )
