"""
Health check endpoints
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.models.response import HealthResponse
from app.services.gemini import gemini_service
from app.services.prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and its dependencies",
)
async def health_check():
    """
    Health check endpoint that verifies:
    - API is running
    - Gemini API is accessible
    - Configuration is loaded properly
    - Available models and prompts
    """

    try:
        settings = get_settings()

        # Test Gemini API connection
        gemini_status = await gemini_service.test_connection()

        # Get prompt manager info
        prompt_manager = get_prompt_manager()
        available_prompts = prompt_manager.get_available_versions()

        # Determine overall status
        overall_status = "healthy" if gemini_status["api_accessible"] else "degraded"

        return HealthResponse(
            status=overall_status,
            version="1.0.0",
            environment=settings.environment,
            gemini_api={
                "status": "connected" if gemini_status["api_accessible"] else "disconnected",
                "models_available": len(gemini_status.get("available_models", [])),
                "test_response": gemini_status.get("test_response"),
                "error": gemini_status.get("error"),
            },
            available_models=gemini_status.get("available_models", []),
            available_prompts=available_prompts,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")

        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            environment="unknown",
            gemini_api={"status": "error", "models_available": 0, "test_response": None, "error": str(e)},
            available_models=[],
            available_prompts=[],
            timestamp=datetime.utcnow().isoformat(),
        )


@router.get("/ready", summary="Readiness check", description="Check if the service is ready to accept requests")
async def readiness_check():
    """
    Readiness check for Kubernetes/container orchestration
    Returns 200 if service is ready, 503 if not ready
    """

    try:
        settings = get_settings()

        # Check critical dependencies
        if not settings.gemini_api_key:
            return {"status": "not_ready", "reason": "Gemini API key not configured"}, 503

        if not settings.api_key:
            return {"status": "not_ready", "reason": "No API keys configured"}, 503

        # Quick test of Gemini API
        gemini_status = await gemini_service.test_connection()
        if not gemini_status["api_accessible"]:
            return {
                "status": "not_ready",
                "reason": "Gemini API not accessible",
                "error": gemini_status.get("error"),
            }, 503

        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "reason": str(e)}, 503


@router.get(
    "/live", summary="Liveness check", description="Check if the service is alive (for Kubernetes liveness probe)"
)
async def liveness_check():
    """
    Liveness check for Kubernetes/container orchestration
    Returns 200 if service is alive, 500 if dead
    """

    try:
        # Simple check that the service is running
        # This should always return 200 unless the service is completely broken
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "unknown",  # Could implement actual uptime tracking
        }

    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return {"status": "dead", "error": str(e)}, 500


@router.get(
    "/metrics", summary="Service metrics", description="Get basic service metrics (could be extended for monitoring)"
)
async def get_metrics():
    """
    Basic metrics endpoint
    Could be extended to integrate with Prometheus/monitoring systems
    """

    try:
        settings = get_settings()

        # Basic metrics - could be extended
        metrics = {
            "service": {"name": "insurance-pdf-extractor", "version": "1.0.0", "environment": settings.environment},
            "configuration": {
                "max_file_size_mb": settings.max_file_size_mb,
                "default_model": settings.default_model,
                "rate_limit": settings.rate_limit_requests,
            },
            "api": {"configured_keys": len(settings.api_key), "gemini_configured": bool(settings.gemini_api_key)},
            "timestamp": datetime.utcnow().isoformat(),
        }

        return metrics

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {"error": str(e)}, 500
