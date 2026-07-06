from fastapi import FastAPI

app = FastAPI(title="MatrixLoop")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matrixloop"}
