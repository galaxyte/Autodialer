"""
FastAPI application entry point for the Autodialer project.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from .models.call_log import Base
from .routes.ai_prompt import router as ai_router
from .routes.calls import router as calls_router
from .services.ai_service import AIService
from .services.twilio_service import TwilioService


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./autodialer.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    twilio_service = TwilioService()
    ai_service = AIService()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.db_engine = engine
    app.state.async_session = session_factory
    app.state.twilio_service = twilio_service
    app.state.ai_service = ai_service

    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Autodialer", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calls_router)
app.include_router(ai_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

