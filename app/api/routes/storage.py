# app/api/routes/storage.py
"""
API routes for stored extraction data
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_user
from app.services.storage import storage_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/extractions",
    summary="Get recent extractions",
    description="Retrieve recent extraction records with optional filtering",
)
async def get_extractions(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of records to return"),
    filename_pattern: Optional[str] = Query(default=None, description="Filter by filename pattern"),
    status: Optional[str] = Query(default=None, description="Filter by extraction status"),
    model_used: Optional[str] = Query(default=None, description="Filter by model used"),
    current_user: dict = Depends(get_current_user),
):
    """Get recent extraction records with optional filtering"""

    try:
        if filename_pattern or status or model_used:
            # Use search functionality if filters are provided
            extractions = storage_service.search_extractions(
                filename_pattern=filename_pattern, status=status, model_used=model_used, limit=limit
            )
        else:
            # Get recent extractions
            extractions = storage_service.get_recent_extractions(limit=limit)

        return {"extractions": extractions, "total_returned": len(extractions), "limit": limit}

    except Exception as e:
        logger.error(f"Failed to get extractions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve extraction records"
        )


@router.get(
    "/extractions/{extraction_id}",
    summary="Get specific extraction",
    description="Retrieve a specific extraction record by ID",
)
async def get_extraction(
    extraction_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific extraction record by ID"""

    try:
        extraction = storage_service.get_extraction(extraction_id)

        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Extraction with ID {extraction_id} not found"
            )

        return extraction

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get extraction {extraction_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve extraction record"
        )


@router.get(
    "/statistics", summary="Get extraction statistics", description="Get statistics about stored extraction data"
)
async def get_statistics(
    current_user: dict = Depends(get_current_user),
):
    """Get statistics about stored extraction data"""

    try:
        stats = storage_service.get_field_statistics()
        return stats

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve statistics")


@router.post(
    "/cleanup", summary="Clean up old records", description="Remove old extraction records to free up storage space"
)
async def cleanup_old_records(
    days_to_keep: int = Query(default=90, ge=1, le=365, description="Number of days to keep records"),
    current_user: dict = Depends(get_current_user),
):
    """Clean up old extraction records"""

    try:
        deleted_count = storage_service.cleanup_old_records(days_to_keep)

        return {
            "message": f"Successfully cleaned up {deleted_count} old records",
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
        }

    except Exception as e:
        logger.error(f"Failed to cleanup records: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cleanup old records")


@router.get("/export", summary="Export extraction data", description="Export extraction data in various formats")
async def export_extractions(
    format: str = Query(default="json", regex="^(json|csv)$", description="Export format (json or csv)"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """Export extraction data in JSON or CSV format"""

    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date format. Use YYYY-MM-DD"
                )

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date format. Use YYYY-MM-DD"
                )

        # Get extractions with date filtering
        extractions = storage_service.search_extractions(
            start_date=start_dt, end_date=end_dt, limit=10000  # Large limit for export
        )

        if format == "json":
            return {
                "extractions": extractions,
                "export_date": datetime.now().isoformat(),
                "total_records": len(extractions),
                "date_range": {"start": start_date, "end": end_date},
            }

        elif format == "csv":
            # Convert to CSV format
            import csv
            import io

            output = io.StringIO()
            if extractions:
                fieldnames = [
                    "id",
                    "filename",
                    "status",
                    "model_used",
                    "prompt_version",
                    "processing_time",
                    "created_at",
                    "user_key",
                ]

                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()

                for extraction in extractions:
                    # Extract only the basic fields for CSV
                    row = {field: extraction.get(field, "") for field in fieldnames}
                    writer.writerow(row)

            csv_content = output.getvalue()
            output.close()

            from fastapi.responses import Response

            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=extractions_{datetime.now().strftime('%Y%m%d')}.csv"
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export extractions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to export extraction data"
        )
