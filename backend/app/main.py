from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(title="MatrixLoop")
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matrixloop"}
