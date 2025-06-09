"""
Main FastAPI application for Insurance PDF Extractor
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from fastapi_mcp import FastApiMCP
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import analytics, extraction, health, storage

# from app.api.routes.analytics import router as analytics_router
from app.core.config import get_settings
from app.core.exceptions import setup_exception_handlers

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Insurance PDF Extractor API")

    # Initialize storage service on startup
    try:
        from app.services.storage import storage_service

        logger.info("Storage service initialized")

        # Check if database needs migration (optional - for development)
        try:
            with storage_service._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(extractions)")
                columns = [column[1] for column in cursor.fetchall()]

                if "input_tokens" not in columns:
                    logger.warning("Database appears to need migration for token usage tracking")
                    logger.warning("Run: python scripts/migrate_database.py")
                else:
                    logger.info("Database schema is up to date with token usage tracking")

        except Exception as e:
            logger.warning(f"Could not check database schema: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize storage service: {e}")

    yield
    logger.info("Shutting down Insurance PDF Extractor API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()

    app = FastAPI(
        title="Insurance PDF Extractor API",
        description="Extract structured data from insurance quote PDFs using Gemini AI",
        version="1.0.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None,
        lifespan=lifespan,
    )

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Setup exception handlers
    setup_exception_handlers(app)

    # Include routers
    app.include_router(health.router, prefix="/health", tags=["Health"])
    app.include_router(extraction.router, prefix="/api/v1", tags=["Extraction"])
    app.include_router(storage.router, prefix="/api/v1/storage", tags=["Storage"])
    app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

    return app


app = create_app()

# Add MCP server to the FastAPI app (disabled for Docker)
# mcp = FastApiMCP(app)

# Mount the MCP server to the FastAPI app (disabled for Docker)
# mcp.mount()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
