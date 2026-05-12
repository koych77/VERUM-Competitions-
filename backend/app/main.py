import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.bot.main import start_bot_background_task
from app.config import get_settings
from app.database import init_db
from app.routers import auth, broadcasts, events, profiles, registrations

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bot_task = start_bot_background_task()
    yield
    if bot_task:
        bot_task.cancel()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
settings.upload_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(broadcasts.router)
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
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist: Path = settings.frontend_dist
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(
            frontend_dist / "index.html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    app.mount("/", StaticFiles(directory=frontend_dist), name="frontend")
