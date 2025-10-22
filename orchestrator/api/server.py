from __future__ import annotations
from fastapi import FastAPI
from .healthcheck import app as health_app
from .control import router as control_router

api = FastAPI(title="Orchestrator-Alpha v1")
api.mount("/", health_app)
api.include_router(control_router)
