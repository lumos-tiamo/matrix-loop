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

os.makedirs(settings.video_output_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.video_output_dir), name="media")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matrixloop"}
