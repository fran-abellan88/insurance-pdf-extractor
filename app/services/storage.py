"""
Local storage service for extracted PDF data
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LocalStorageService:
    """Service for storing extracted PDF data locally"""

    def __init__(self, db_path: str = "data/extractions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._initialize_database()

    def _initialize_database(self):
        """Initialize the SQLite database with required tables"""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_size INTEGER,
                    status TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    prompt_version TEXT,
                    processing_time REAL,
                    extracted_data TEXT,  -- JSON string
                    confidence_scores TEXT,  -- JSON string
                    failed_fields TEXT,  -- JSON string
                    warnings TEXT,  -- JSON string
                    user_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extraction_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    extraction_id INTEGER,
                    field_name TEXT NOT NULL,
                    field_value TEXT,
                    confidence_score REAL,
                    is_failed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (extraction_id) REFERENCES extractions (id)
                )
            """
            )

            # Create indexes for better performance
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extractions_filename
                ON extractions(filename)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extractions_created_at
                ON extractions(created_at)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fields_extraction_id
                ON extraction_fields(extraction_id)
            """
            )

    @contextmanager
    def _get_connection(self):
        """Get database connection with automatic closing"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()

    def store_extraction(
        self,
        filename: str,
        file_size: int,
        status: str,
        model_used: str,
        prompt_version: str,
        processing_time: float,
        extracted_data: Dict[str, Any],
        confidence_scores: Optional[Dict[str, float]] = None,
        failed_fields: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        user_key: Optional[str] = None,
    ) -> int:
        """
        Store extraction results in the database

        Returns:
            The ID of the stored extraction record
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Insert main extraction record
                cursor.execute(
                    """
                    INSERT INTO extractions (
                        filename, file_size, status, model_used, prompt_version,
                        processing_time, extracted_data, confidence_scores,
                        failed_fields, warnings, user_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        filename,
                        file_size,
                        status,
                        model_used,
                        prompt_version,
                        processing_time,
                        json.dumps(extracted_data) if extracted_data else None,
                        json.dumps(confidence_scores) if confidence_scores else None,
                        json.dumps(failed_fields) if failed_fields else None,
                        json.dumps(warnings) if warnings else None,
                        user_key,
                    ),
                )

                extraction_id = cursor.lastrowid

                # Insert individual field records
                if extracted_data:
                    for field_name, field_value in extracted_data.items():
                        confidence = confidence_scores.get(field_name) if confidence_scores else None
                        is_failed = field_name in (failed_fields or [])

                        cursor.execute(
                            """
                            INSERT INTO extraction_fields (
                                extraction_id, field_name, field_value,
                                confidence_score, is_failed
                            ) VALUES (?, ?, ?, ?, ?)
                        """,
                            (
                                extraction_id,
                                field_name,
                                str(field_value) if field_value is not None else None,
                                confidence,
                                is_failed,
                            ),
                        )

                conn.commit()
                logger.info(f"Stored extraction record with ID: {extraction_id}")
                return extraction_id

        except Exception as e:
            logger.error(f"Failed to store extraction: {e}")
            raise

    def get_extraction(self, extraction_id: int) -> Optional[Dict[str, Any]]:
        """Get extraction record by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM extractions WHERE id = ?
                """,
                    (extraction_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                return self._row_to_dict(row)

        except Exception as e:
            logger.error(f"Failed to get extraction {extraction_id}: {e}")
            return None

    def get_recent_extractions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent extraction records"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM extractions
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

                return [self._row_to_dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get recent extractions: {e}")
            return []

    def search_extractions(
        self,
        filename_pattern: Optional[str] = None,
        status: Optional[str] = None,
        model_used: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search extraction records with filters"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM extractions WHERE 1=1"
                params = []

                if filename_pattern:
                    query += " AND filename LIKE ?"
                    params.append(f"%{filename_pattern}%")

                if status:
                    query += " AND status = ?"
                    params.append(status)

                if model_used:
                    query += " AND model_used = ?"
                    params.append(model_used)

                if start_date:
                    query += " AND created_at >= ?"
                    params.append(start_date.isoformat())

                if end_date:
                    query += " AND created_at <= ?"
                    params.append(end_date.isoformat())

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                return [self._row_to_dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to search extractions: {e}")
            return []

    def get_field_statistics(self) -> Dict[str, Any]:
        """Get statistics about extracted fields"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total extractions
                cursor.execute("SELECT COUNT(*) FROM extractions")
                total_extractions = cursor.fetchone()[0]

                # Success rate
                cursor.execute(
                    """
                    SELECT
                        status,
                        COUNT(*) as count,
                        ROUND(COUNT(*) * 100.0 / ?, 2) as percentage
                    FROM extractions
                    GROUP BY status
                """,
                    (total_extractions,),
                )

                status_stats = [{"status": row[0], "count": row[1], "percentage": row[2]} for row in cursor.fetchall()]

                # Field success rates
                cursor.execute(
                    """
                    SELECT
                        field_name,
                        COUNT(*) as total_occurrences,
                        SUM(CASE WHEN is_failed = 0 AND field_value IS NOT NULL
                            AND field_value != 'EMPTY VALUE' THEN 1 ELSE 0 END) as successful,
                        ROUND(SUM(CASE WHEN is_failed = 0 AND field_value IS NOT NULL
                            AND field_value != 'EMPTY VALUE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as success_rate
                    FROM extraction_fields
                    GROUP BY field_name
                    ORDER BY success_rate DESC
                """
                )

                field_stats = [
                    {"field_name": row[0], "total_occurrences": row[1], "successful": row[2], "success_rate": row[3]}
                    for row in cursor.fetchall()
                ]

                return {
                    "total_extractions": total_extractions,
                    "status_breakdown": status_stats,
                    "field_success_rates": field_stats,
                }

        except Exception as e:
            logger.error(f"Failed to get field statistics: {e}")
            return {}

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite row to dictionary"""
        result = dict(row)

        # Parse JSON fields
        json_fields = ["extracted_data", "confidence_scores", "failed_fields", "warnings"]
        for field in json_fields:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    result[field] = None

        return result

    def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """Clean up old extraction records"""
        try:
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Delete old extraction fields first (foreign key constraint)
                cursor.execute(
                    """
                    DELETE FROM extraction_fields
                    WHERE extraction_id IN (
                        SELECT id FROM extractions
                        WHERE created_at < ?
                    )
                """,
                    (cutoff_date.isoformat(),),
                )

                # Delete old extractions
                cursor.execute(
                    """
                    DELETE FROM extractions
                    WHERE created_at < ?
                """,
                    (cutoff_date.isoformat(),),
                )

                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted_count} old extraction records")
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
            return 0


# Global storage service instance
storage_service = LocalStorageService()
