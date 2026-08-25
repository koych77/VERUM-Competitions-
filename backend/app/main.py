import logging
from asyncio import CancelledError
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bot.main import (
    feed_webhook_update,
    setup_bot_webhook,
    shutdown_bot,
    start_bot_background_task,
    webhook_path,
    webhook_secret,
)
from app.config import get_settings
from app.database import get_db, init_db
from app.routers import auth, broadcasts, directories, events, profiles, registrations

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    init_db()
    await setup_bot_webhook()
    bot_task = start_bot_background_task()
    yield
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except CancelledError:
            pass
    await shutdown_bot()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
settings.upload_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(broadcasts.router)
app.include_router(directories.router)
app.include_router(directories.public_router)
app.include_router(events.router)
app.include_router(profiles.router)
app.include_router(registrations.router)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.middleware("http")
async def no_stale_app_shell(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob: https:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' https://telegram.org; "
        "connect-src 'self' https:; frame-ancestors https://web.telegram.org https://*.telegram.org"
    )
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.post(webhook_path())
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)) -> dict[str, bool]:
    if x_telegram_bot_api_secret_token != webhook_secret():
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    await feed_webhook_update(await request.json())
    return {"ok": True}


frontend_dist: Path = settings.frontend_dist
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def frontend_app(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        requested_file = (frontend_dist / full_path).resolve()
        try:
            requested_file.relative_to(frontend_dist.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Файл не найден") from exc

        if full_path and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(
            frontend_dist / "index.html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
