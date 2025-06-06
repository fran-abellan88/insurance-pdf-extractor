"""
API routes for token usage and cost analytics
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_user
from app.services.storage import storage_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/overview",
    summary="Get token usage overview",
    description="Get comprehensive overview of token usage and costs across all extractions",
)
async def get_token_usage_overview(
    current_user: dict = Depends(get_current_user),
):
    """Get comprehensive token usage statistics"""

    try:
        stats = storage_service.get_token_usage_statistics()

        if not stats:
            return {
                "message": "No token usage data available",
                "overall_statistics": {},
                "statistics_by_model": [],
                "daily_cost_trends": [],
                "most_expensive_extractions": [],
            }

        return {
            "token_usage_analytics": stats,
            "summary": {
                "total_extractions_tracked": stats.get("overall_statistics", {}).get(
                    "total_extractions_with_tokens", 0
                ),
                "total_cost": stats.get("overall_statistics", {}).get("total_estimated_cost", 0),
                "most_used_model": _get_most_used_model(stats.get("statistics_by_model", [])),
                "cost_trend": _analyze_cost_trend(stats.get("daily_cost_trends", [])),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get token usage overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve token usage analytics"
        )


@router.get(
    "/by-model",
    summary="Get token usage by model",
    description="Get detailed breakdown of token usage and costs by AI model",
)
async def get_token_usage_by_model(
    model_name: Optional[str] = Query(default=None, description="Filter by specific model"),
    current_user: dict = Depends(get_current_user),
):
    """Get token usage statistics grouped by model"""

    try:
        stats = storage_service.get_token_usage_statistics()
        model_stats = stats.get("statistics_by_model", [])

        if model_name:
            model_stats = [stat for stat in model_stats if stat["model_used"] == model_name]
            if not model_stats:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"No data found for model: {model_name}"
                )

        # Calculate additional metrics
        for stat in model_stats:
            if stat["extraction_count"] > 0:
                stat["avg_tokens_per_extraction"] = (stat["total_input_tokens"] + stat["total_output_tokens"]) / stat[
                    "extraction_count"
                ]
                stat["cost_per_1k_tokens"] = (
                    stat["total_cost"] / ((stat["total_input_tokens"] + stat["total_output_tokens"]) / 1000)
                    if stat["total_input_tokens"] + stat["total_output_tokens"] > 0
                    else 0
                )

        return {
            "model_statistics": model_stats,
            "filtered_by_model": model_name,
            "total_models": len(model_stats),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get token usage by model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve model statistics"
        )


@router.get(
    "/trends",
    summary="Get cost and usage trends",
    description="Get time-based trends for token usage and costs",
)
async def get_usage_trends(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
):
    """Get token usage and cost trends over time"""

    try:
        # Get trends from storage service
        stats = storage_service.get_token_usage_statistics()
        daily_trends = stats.get("daily_cost_trends", [])

        # Filter by requested days
        cutoff_date = datetime.now() - timedelta(days=days)
        daily_trends = [trend for trend in daily_trends if datetime.strptime(trend["date"], "%Y-%m-%d") >= cutoff_date]

        # Calculate trend analysis
        if len(daily_trends) >= 2:
            recent_avg = sum(trend["daily_cost"] for trend in daily_trends[:7]) / min(7, len(daily_trends))
            older_avg = sum(trend["daily_cost"] for trend in daily_trends[-7:]) / min(7, len(daily_trends))
            cost_trend = (
                "increasing" if recent_avg > older_avg else "decreasing" if recent_avg < older_avg else "stable"
            )
        else:
            cost_trend = "insufficient_data"

        return {
            "daily_trends": daily_trends,
            "period_days": days,
            "trend_analysis": {
                "cost_trend": cost_trend,
                "total_cost_in_period": sum(trend["daily_cost"] for trend in daily_trends),
                "total_extractions_in_period": sum(trend["extraction_count"] for trend in daily_trends),
                "avg_daily_cost": sum(trend["daily_cost"] for trend in daily_trends) / max(1, len(daily_trends)),
                "avg_daily_extractions": sum(trend["extraction_count"] for trend in daily_trends)
                / max(1, len(daily_trends)),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get usage trends: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve usage trends")


@router.get(
    "/expensive",
    summary="Get most expensive extractions",
    description="Get list of extractions with highest token costs",
)
async def get_expensive_extractions(
    limit: int = Query(default=10, ge=1, le=100, description="Number of records to return"),
    min_cost: Optional[float] = Query(default=None, ge=0, description="Minimum cost threshold"),
    current_user: dict = Depends(get_current_user),
):
    """Get most expensive extractions by token cost"""

    try:
        stats = storage_service.get_token_usage_statistics()
        expensive_extractions = stats.get("most_expensive_extractions", [])

        # Filter by minimum cost if specified
        if min_cost is not None:
            expensive_extractions = [
                extraction for extraction in expensive_extractions if extraction["estimated_cost"] >= min_cost
            ]

        # Limit results
        expensive_extractions = expensive_extractions[:limit]

        # Calculate additional metrics
        total_cost = sum(extraction["estimated_cost"] for extraction in expensive_extractions)
        avg_cost = total_cost / len(expensive_extractions) if expensive_extractions else 0

        return {
            "expensive_extractions": expensive_extractions,
            "limit": limit,
            "min_cost_filter": min_cost,
            "summary": {
                "total_extractions": len(expensive_extractions),
                "total_cost": total_cost,
                "average_cost": avg_cost,
                "highest_cost": expensive_extractions[0]["estimated_cost"] if expensive_extractions else 0,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get expensive extractions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve expensive extractions"
        )


@router.get(
    "/cost-prediction",
    summary="Predict costs for planned extractions",
    description="Estimate costs for a given number of planned extractions based on historical data",
)
async def predict_extraction_costs(
    planned_extractions: int = Query(..., ge=1, le=10000, description="Number of planned extractions"),
    model_name: Optional[str] = Query(default=None, description="Specific model to use for prediction"),
    current_user: dict = Depends(get_current_user),
):
    """Predict costs for planned extractions based on historical averages"""

    try:
        stats = storage_service.get_token_usage_statistics()
        model_stats = stats.get("statistics_by_model", [])

        if model_name:
            # Filter to specific model
            model_data = [stat for stat in model_stats if stat["model_used"] == model_name]
            if not model_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"No historical data found for model: {model_name}"
                )
            avg_cost_per_extraction = model_data[0]["avg_cost"]
            model_used = model_name
        else:
            # Use overall average
            overall_stats = stats.get("overall_statistics", {})
            avg_cost_per_extraction = overall_stats.get("avg_cost_per_extraction", 0)
            model_used = "all_models"

        if avg_cost_per_extraction is None or avg_cost_per_extraction == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient historical data for cost prediction"
            )

        # Calculate predictions
        estimated_total_cost = planned_extractions * avg_cost_per_extraction

        # Cost ranges (±20% for uncertainty)
        cost_range_low = estimated_total_cost * 0.8
        cost_range_high = estimated_total_cost * 1.2

        return {
            "prediction": {
                "planned_extractions": planned_extractions,
                "model_used_for_prediction": model_used,
                "avg_cost_per_extraction": avg_cost_per_extraction,
                "estimated_total_cost": estimated_total_cost,
                "cost_range": {
                    "low": cost_range_low,
                    "high": cost_range_high,
                },
                "confidence": "medium" if len(model_stats) > 0 else "low",
            },
            "assumptions": [
                "Prediction based on historical average costs",
                "Actual costs may vary based on document complexity",
                "Cost ranges include ±20% uncertainty margin",
                f"Based on {overall_stats.get('total_extractions_with_tokens', 0)} historical extractions",
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to predict extraction costs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate cost prediction"
        )


@router.get(
    "/export",
    summary="Export token usage data",
    description="Export detailed token usage data in CSV or JSON format",
)
async def export_token_usage_data(
    format: str = Query(default="json", pattern="^(json|csv)$", description="Export format"),
    include_details: bool = Query(default=True, description="Include detailed breakdown"),
    current_user: dict = Depends(get_current_user),
):
    """Export token usage and cost data"""

    try:
        stats = storage_service.get_token_usage_statistics()

        if format == "json":
            export_data = {
                "export_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "export_format": "json",
                    "include_details": include_details,
                },
                "token_usage_analytics": stats,
            }

            if not include_details:
                # Remove detailed arrays to reduce size
                export_data["token_usage_analytics"].pop("daily_cost_trends", None)
                export_data["token_usage_analytics"].pop("most_expensive_extractions", None)

            return export_data

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()

            # Export model statistics as CSV
            if stats.get("statistics_by_model"):
                fieldnames = [
                    "model_used",
                    "extraction_count",
                    "total_input_tokens",
                    "total_output_tokens",
                    "total_cost",
                    "avg_cost",
                    "avg_input_tokens",
                    "avg_output_tokens",
                ]

                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()

                for model_stat in stats["statistics_by_model"]:
                    writer.writerow({field: model_stat.get(field, "") for field in fieldnames})

            csv_content = output.getvalue()
            output.close()

            from fastapi.responses import Response

            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=token_usage_{datetime.now().strftime('%Y%m%d')}.csv"
                },
            )

    except Exception as e:
        logger.error(f"Failed to export token usage data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to export token usage data"
        )


@router.get(
    "/document-types",
    summary="Get document type analytics",
    description="Get comprehensive analytics on document types being processed",
)
async def get_document_type_analytics(
    current_user: dict = Depends(get_current_user),
):
    """Get document type distribution and analytics"""

    try:
        stats = storage_service.get_document_type_statistics()

        if not stats:
            return {
                "message": "No document type data available",
                "document_type_distribution": [],
                "daily_trends_by_type": [],
                "model_usage_by_type": [],
            }

        # Calculate summary metrics
        total_extractions = sum(
            doc_type["total_extractions"] for doc_type in stats.get("document_type_distribution", [])
        )
        
        most_common_type = "unknown"
        if stats.get("document_type_distribution"):
            most_common_type = max(
                stats["document_type_distribution"], 
                key=lambda x: x["total_extractions"]
            )["document_type"]

        return {
            "document_type_analytics": stats,
            "summary": {
                "total_extractions": total_extractions,
                "total_document_types": len(stats.get("document_type_distribution", [])),
                "most_common_type": most_common_type,
                "supported_types": ["quote", "binder"],
            },
        }

    except Exception as e:
        logger.error(f"Failed to get document type analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve document type analytics"
        )


def _get_most_used_model(model_stats: list) -> str:
    """Helper function to get the most used model"""
    if not model_stats:
        return "No data"

    most_used = max(model_stats, key=lambda x: x.get("extraction_count", 0))
    return most_used.get("model_used", "Unknown")


def _analyze_cost_trend(daily_trends: list) -> str:
    """Helper function to analyze cost trends"""
    if len(daily_trends) < 7:
        return "insufficient_data"

    recent_costs = [trend["daily_cost"] for trend in daily_trends[:7]]
    older_costs = [trend["daily_cost"] for trend in daily_trends[-7:]]

    recent_avg = sum(recent_costs) / len(recent_costs)
    older_avg = sum(older_costs) / len(older_costs)

    if recent_avg > older_avg * 1.1:
        return "increasing"
    elif recent_avg < older_avg * 0.9:
        return "decreasing"
    else:
        return "stable"
