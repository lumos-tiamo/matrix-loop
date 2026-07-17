import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings

app = FastAPI(title="MatrixLoop")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

_media_dir = os.path.abspath(settings.video_output_dir)
os.makedirs(_media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")

# 图文 carousels (PNG slide folders) served for the frontend 图文 gallery
_carousel_dir = os.path.abspath(os.path.join(os.path.dirname(_media_dir), "carousels"))
os.makedirs(_carousel_dir, exist_ok=True)
app.mount("/carousels", StaticFiles(directory=_carousel_dir), name="carousels")


@app.on_event("startup")
def _maybe_autostart_scheduler() -> None:
    from app.config import settings
    if settings.scheduler_autostart:
        from app.scheduler.control import start_scheduler
        from app.db import SessionLocal
        start_scheduler(SessionLocal)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matrixloop"}
