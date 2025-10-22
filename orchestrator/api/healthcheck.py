from __future__ import annotations
from fastapi import FastAPI
from ..telemetry import metrics as METRICS

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/metrics")
async def metrics():
    return METRICS.snapshot()
