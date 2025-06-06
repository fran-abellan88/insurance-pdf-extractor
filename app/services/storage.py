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
                    document_type TEXT DEFAULT 'quote',  -- Document type
                    processing_time REAL,
                    extracted_data TEXT,  -- JSON string
                    confidence_scores TEXT,  -- JSON string
                    failed_fields TEXT,  -- JSON string
                    warnings TEXT,  -- JSON string
                    user_key TEXT,
                    input_tokens INTEGER DEFAULT NULL,
                    output_tokens INTEGER DEFAULT NULL,
                    total_tokens INTEGER DEFAULT NULL,
                    estimated_cost REAL DEFAULT NULL,
                    cost_breakdown TEXT DEFAULT NULL,
                    token_error TEXT DEFAULT NULL,  -- If token counting failed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # New table for detailed token metrics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    extraction_id INTEGER,
                    model_name TEXT NOT NULL,
                    prompt_token_count INTEGER DEFAULT NULL,
                    candidates_token_count INTEGER DEFAULT NULL,
                    total_token_count INTEGER DEFAULT NULL,
                    input_cost REAL DEFAULT NULL,
                    output_cost REAL DEFAULT NULL,
                    total_cost REAL DEFAULT NULL,
                    pricing_per_1k_input REAL DEFAULT NULL,
                    pricing_per_1k_output REAL DEFAULT NULL,
                    cost_calculation_method TEXT DEFAULT NULL,  -- 'actual' or 'estimated'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (extraction_id) REFERENCES extractions (id)
                )
            """
            )

            # Enhanced extraction_fields table (keep existing structure)
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
                CREATE INDEX IF NOT EXISTS idx_extractions_model_used
                ON extractions(model_used)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_token_usage_extraction_id
                ON token_usage(extraction_id)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fields_extraction_id
                ON extraction_fields(extraction_id)
            """
            )

            # Add new columns to existing extractions table if they don't exist
            self._add_columns_if_not_exist(conn)

    def _add_columns_if_not_exist(self, conn):
        """Add new token-related columns to existing extractions table"""
        # Check if token columns exist, add them if they don't
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(extractions)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        columns_to_add = [
            ("input_tokens", "INTEGER DEFAULT NULL"),
            ("output_tokens", "INTEGER DEFAULT NULL"),
            ("total_tokens", "INTEGER DEFAULT NULL"),
            ("estimated_cost", "REAL DEFAULT NULL"),
            ("cost_breakdown", "TEXT DEFAULT NULL"),
            ("token_error", "TEXT DEFAULT NULL"),
            ("document_type", "TEXT DEFAULT 'quote'"),
        ]

        for column_name, column_def in columns_to_add:
            if column_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE extractions ADD COLUMN {column_name} {column_def}")
                    logger.info(f"Added column {column_name} to extractions table")
                except sqlite3.Error as e:
                    logger.warning(f"Could not add column {column_name}: {e}")

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
        token_usage: Optional[Dict[str, Any]] = None,
        document_type: str = "quote",  # New parameter
    ) -> int:
        """
        Store extraction results in the database with token usage and document type

        Args:
            document_type: Type of document processed (e.g., 'quote', 'binder')
            token_usage: Dictionary containing token usage information
                Expected keys: input_tokens, output_tokens, total_tokens,
                              estimated_cost, cost_breakdown, error

        Returns:
            The ID of the stored extraction record
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Extract token usage data
                input_tokens = None
                output_tokens = None
                total_tokens = None
                estimated_cost = None
                cost_breakdown_json = None
                token_error = None

                if token_usage:
                    input_tokens = token_usage.get("prompt_token_count") or token_usage.get("input_tokens")
                    output_tokens = token_usage.get("candidates_token_count") or token_usage.get("output_tokens")
                    total_tokens = token_usage.get("total_token_count") or token_usage.get("total_tokens")
                    estimated_cost = token_usage.get("estimated_cost")
                    token_error = token_usage.get("error")

                    if token_usage.get("cost_breakdown"):
                        cost_breakdown_json = json.dumps(token_usage["cost_breakdown"])

                # Insert main extraction record with token data
                cursor.execute(
                    """
                    INSERT INTO extractions (
                        filename, file_size, status, model_used, prompt_version,
                        document_type, processing_time, extracted_data, confidence_scores,
                        failed_fields, warnings, user_key,
                        input_tokens, output_tokens, total_tokens,
                        estimated_cost, cost_breakdown, token_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        filename,
                        file_size,
                        status,
                        model_used,
                        prompt_version,
                        document_type,
                        processing_time,
                        json.dumps(extracted_data) if extracted_data else None,
                        json.dumps(confidence_scores) if confidence_scores else None,
                        json.dumps(failed_fields) if failed_fields else None,
                        json.dumps(warnings) if warnings else None,
                        user_key,
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        estimated_cost,
                        cost_breakdown_json,
                        token_error,
                    ),
                )

                extraction_id = cursor.lastrowid

                # Insert detailed token usage record if available
                if token_usage and not token_error:
                    cost_breakdown = token_usage.get("cost_breakdown", {})

                    cursor.execute(
                        """
                        INSERT INTO token_usage (
                            extraction_id, model_name, prompt_token_count,
                            candidates_token_count, total_token_count,
                            input_cost, output_cost, total_cost,
                            pricing_per_1k_input, pricing_per_1k_output,
                            cost_calculation_method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            extraction_id,
                            model_used,
                            input_tokens,
                            output_tokens,
                            total_tokens,
                            cost_breakdown.get("input_cost"),
                            cost_breakdown.get("output_cost"),
                            cost_breakdown.get("total_cost"),
                            cost_breakdown.get("pricing_per_1k_tokens", {}).get("input"),
                            cost_breakdown.get("pricing_per_1k_tokens", {}).get("output"),
                            "actual" if token_usage.get("prompt_token_count") else "estimated",
                        ),
                    )

                # Insert individual field records (existing logic)
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

    def get_extraction_with_token_usage(self, extraction_id: int) -> Optional[Dict[str, Any]]:
        """Get extraction record with detailed token usage"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get main extraction record
                cursor.execute(
                    """
                    SELECT * FROM extractions WHERE id = ?
                """,
                    (extraction_id,),
                )

                extraction_row = cursor.fetchone()
                if not extraction_row:
                    return None

                extraction = self._row_to_dict(extraction_row)

                # Get detailed token usage
                cursor.execute(
                    """
                    SELECT * FROM token_usage WHERE extraction_id = ?
                """,
                    (extraction_id,),
                )

                token_row = cursor.fetchone()
                if token_row:
                    extraction["detailed_token_usage"] = dict(token_row)

                return extraction

        except Exception as e:
            logger.error(f"Failed to get extraction {extraction_id}: {e}")
            return None

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
        document_type: Optional[str] = None,
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

                if document_type:
                    query += " AND document_type = ?"
                    params.append(document_type)

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

    def get_token_usage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive token usage and cost statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Overall token statistics
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_extractions_with_tokens,
                        SUM(input_tokens) as total_input_tokens,
                        SUM(output_tokens) as total_output_tokens,
                        SUM(total_tokens) as total_tokens_used,
                        SUM(estimated_cost) as total_estimated_cost,
                        AVG(estimated_cost) as avg_cost_per_extraction,
                        MIN(estimated_cost) as min_cost,
                        MAX(estimated_cost) as max_cost
                    FROM extractions
                    WHERE input_tokens IS NOT NULL
                """
                )

                overall_stats = dict(cursor.fetchone())

                # Statistics by model
                cursor.execute(
                    """
                    SELECT
                        model_used,
                        COUNT(*) as extraction_count,
                        SUM(input_tokens) as total_input_tokens,
                        SUM(output_tokens) as total_output_tokens,
                        SUM(estimated_cost) as total_cost,
                        AVG(estimated_cost) as avg_cost,
                        AVG(input_tokens) as avg_input_tokens,
                        AVG(output_tokens) as avg_output_tokens
                    FROM extractions
                    WHERE input_tokens IS NOT NULL
                    GROUP BY model_used
                    ORDER BY total_cost DESC
                """
                )

                model_stats = [dict(row) for row in cursor.fetchall()]

                # Daily cost trends (last 30 days)
                cursor.execute(
                    """
                    SELECT
                        DATE(created_at) as date,
                        COUNT(*) as extraction_count,
                        SUM(estimated_cost) as daily_cost,
                        SUM(total_tokens) as daily_tokens
                    FROM extractions
                    WHERE input_tokens IS NOT NULL
                        AND created_at >= datetime('now', '-30 days')
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """
                )

                daily_trends = [dict(row) for row in cursor.fetchall()]

                # Most expensive extractions
                cursor.execute(
                    """
                    SELECT
                        id, filename, model_used, estimated_cost,
                        input_tokens, output_tokens, created_at
                    FROM extractions
                    WHERE estimated_cost IS NOT NULL
                    ORDER BY estimated_cost DESC
                    LIMIT 10
                """
                )

                expensive_extractions = [dict(row) for row in cursor.fetchall()]

                return {
                    "overall_statistics": overall_stats,
                    "statistics_by_model": model_stats,
                    "daily_cost_trends": daily_trends,
                    "most_expensive_extractions": expensive_extractions,
                    "generated_at": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get token usage statistics: {e}")
            return {}

    def get_document_type_statistics(self) -> Dict[str, Any]:
        """Get statistics by document type"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Overall document type distribution
                cursor.execute(
                    """
                    SELECT
                        COALESCE(document_type, 'quote') as document_type,
                        COUNT(*) as total_extractions,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_extractions,
                        COUNT(CASE WHEN status = 'partial_success' THEN 1 END) as partial_extractions,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_extractions,
                        AVG(processing_time) as avg_processing_time,
                        SUM(estimated_cost) as total_cost,
                        AVG(estimated_cost) as avg_cost,
                        MIN(created_at) as first_extraction,
                        MAX(created_at) as latest_extraction
                    FROM extractions
                    GROUP BY COALESCE(document_type, 'quote')
                    ORDER BY total_extractions DESC
                """
                )

                document_type_stats = [dict(row) for row in cursor.fetchall()]

                # Document type trends over time (last 30 days)
                cursor.execute(
                    """
                    SELECT
                        DATE(created_at) as date,
                        COALESCE(document_type, 'quote') as document_type,
                        COUNT(*) as daily_count
                    FROM extractions
                    WHERE created_at >= datetime('now', '-30 days')
                    GROUP BY DATE(created_at), COALESCE(document_type, 'quote')
                    ORDER BY date DESC, daily_count DESC
                """
                )

                daily_type_trends = [dict(row) for row in cursor.fetchall()]

                # Model usage by document type
                cursor.execute(
                    """
                    SELECT
                        COALESCE(document_type, 'quote') as document_type,
                        model_used,
                        COUNT(*) as usage_count,
                        AVG(processing_time) as avg_processing_time,
                        AVG(estimated_cost) as avg_cost
                    FROM extractions
                    GROUP BY COALESCE(document_type, 'quote'), model_used
                    ORDER BY usage_count DESC
                """
                )

                model_by_type_stats = [dict(row) for row in cursor.fetchall()]

                return {
                    "document_type_distribution": document_type_stats,
                    "daily_trends_by_type": daily_type_trends,
                    "model_usage_by_type": model_by_type_stats,
                    "generated_at": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get document type statistics: {e}")
            return {}

    def get_field_statistics(self) -> Dict[str, Any]:
        """Enhanced field statistics including token usage"""
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

                # Field success rates (existing logic)
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

                # Token usage summary
                token_stats = self.get_token_usage_statistics()

                return {
                    "total_extractions": total_extractions,
                    "status_breakdown": status_stats,
                    "field_success_rates": field_stats,
                    "token_usage_summary": token_stats.get("overall_statistics", {}),
                }

        except Exception as e:
            logger.error(f"Failed to get field statistics: {e}")
            return {}

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite row to dictionary with enhanced JSON parsing"""
        result = dict(row)

        # Parse JSON fields
        json_fields = ["extracted_data", "confidence_scores", "failed_fields", "warnings", "cost_breakdown"]
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
