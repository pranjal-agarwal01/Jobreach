"""
Jobreach API.

    uvicorn app.main:app --reload --port 8000     # API
    python -m app.worker                           # background pipeline (separate process)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import close_pool
from .routes import factbank, gmail, intake, me, onboarding, work


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(title="Jobreach API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
for r in (me.router, onboarding.router, factbank.router, work.router, intake.router, gmail.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"ok": True}
