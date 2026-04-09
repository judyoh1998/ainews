from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth, digest, ingest, quiz, sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Neko News", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(digest.router, prefix="/api")
    app.include_router(quiz.router, prefix="/api")
    app.include_router(sources.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"ok": True, "has_api_key": bool(settings.anthropic_api_key)}

    # Serve frontend — must be last (catches all non-API routes)
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

    return app


app = create_app()
