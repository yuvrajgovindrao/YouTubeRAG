import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db import init_db
from app.middleware.session import SessionMiddleware
from app.routers import collections, ask
from app.services.cleanup import start_cleanup_scheduler, stop_cleanup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def rate_limit_key(request: Request) -> str:
    """Combines session ID and remote IP for granular rate limiting."""
    session_id = getattr(request.state, "session_id", "anonymous")
    ip = get_remote_address(request)
    return f"{session_id}:{ip}"


limiter = Limiter(
    key_func=rate_limit_key,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[f"{settings.RATE_LIMIT_PER_HOUR}/hour"] if settings.RATE_LIMIT_ENABLED else []
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up YouTube RAG Backend...")
    # Initialize pgvector and DB schema
    await init_db()
    # Start periodic session cleanup
    start_cleanup_scheduler()
    yield
    logger.info("Shutting down YouTube RAG Backend...")
    stop_cleanup_scheduler()


app = FastAPI(
    title="YouTube RAG Assistant API",
    description="Multi-video YouTube RAG backend with timestamp-grounded retrieval",
    version="1.0.0",
    lifespan=lifespan
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_origin_regex=r"https?://.*" if settings.ENVIRONMENT == "development" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Id", "Content-Range", "Range"],
)

# 2. Session Middleware
app.add_middleware(SessionMiddleware)

# Routers
app.include_router(collections.router)
app.include_router(ask.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "max_videos_per_collection": settings.MAX_VIDEOS_PER_COLLECTION,
        "rate_limiting": settings.RATE_LIMIT_ENABLED,
        "gemini_chat_model": settings.GEMINI_CHAT_MODEL,
        "gemini_embedding_model": settings.GEMINI_EMBEDDING_MODEL,
    }
