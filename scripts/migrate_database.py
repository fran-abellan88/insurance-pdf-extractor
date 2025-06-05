#!/usr/bin/env python3
"""
Database migration script to add token usage tracking to existing databases
"""

import sqlite3
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.storage import storage_service


def migrate_database():
    """Migrate existing database to include token usage tracking"""

    print("Starting database migration for token usage tracking...")

    try:
        with storage_service._get_connection() as conn:
            cursor = conn.cursor()

            # Check current database schema
            cursor.execute("PRAGMA table_info(extractions)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            print(f"Current extractions table columns: {existing_columns}")

            # Add new columns if they don't exist
            new_columns = [
                ("input_tokens", "INTEGER DEFAULT NULL"),
                ("output_tokens", "INTEGER DEFAULT NULL"),
                ("total_tokens", "INTEGER DEFAULT NULL"),
                ("estimated_cost", "REAL DEFAULT NULL"),
                ("cost_breakdown", "TEXT DEFAULT NULL"),
                ("token_error", "TEXT DEFAULT NULL"),
            ]

            columns_added = 0
            for column_name, column_def in new_columns:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE extractions ADD COLUMN {column_name} {column_def}")
                        print(f"✓ Added column: {column_name}")
                        columns_added += 1
                    except sqlite3.Error as e:
                        print(f"✗ Failed to add column {column_name}: {e}")
                else:
                    print(f"- Column {column_name} already exists")

            # Create token_usage table if it doesn't exist
            cursor.execute(
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
                    cost_calculation_method TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (extraction_id) REFERENCES extractions (id)
                )
            """
            )

            # Check if token_usage table was created
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'")
            if cursor.fetchone():
                print("✓ Created token_usage table")
            else:
                print("- token_usage table already exists")

            # Create indexes for better performance
            indexes_to_create = [
                (
                    "idx_extractions_model_used",
                    "CREATE INDEX IF NOT EXISTS idx_extractions_model_used ON extractions(model_used)",
                ),
                (
                    "idx_token_usage_extraction_id",
                    "CREATE INDEX IF NOT EXISTS idx_token_usage_extraction_id ON token_usage(extraction_id)",
                ),
                (
                    "idx_extractions_cost",
                    "CREATE INDEX IF NOT EXISTS idx_extractions_cost ON extractions(estimated_cost)",
                ),
                (
                    "idx_extractions_tokens",
                    "CREATE INDEX IF NOT EXISTS idx_extractions_tokens ON extractions(total_tokens)",
                ),
            ]

            for index_name, index_sql in indexes_to_create:
                try:
                    cursor.execute(index_sql)
                    print(f"✓ Created index: {index_name}")
                except sqlite3.Error as e:
                    print(f"- Index {index_name} already exists or failed: {e}")

            conn.commit()

            # Get database statistics
            cursor.execute("SELECT COUNT(*) FROM extractions")
            total_extractions = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM extractions WHERE input_tokens IS NOT NULL")
            extractions_with_tokens = cursor.fetchone()[0]

            print("Migration completed successfully!")
            print("Database statistics:")
            print(f"  - Total extractions: {total_extractions}")
            print(f"  - Extractions with token data: {extractions_with_tokens}")
            print(f"  - New columns added: {columns_added}")
            print(f"  - Database path: {storage_service.db_path}")

            if extractions_with_tokens == 0 and total_extractions > 0:
                print(f"\nNote: Existing {total_extractions} extractions don't have token usage data.")
                print("Token tracking will begin with new extractions that include token usage information.")

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False

    return True


def verify_migration():
    """Verify that the migration was successful"""

    print("\nVerifying migration...")

    try:
        with storage_service._get_connection() as conn:
            cursor = conn.cursor()

            # Check extractions table structure
            cursor.execute("PRAGMA table_info(extractions)")
            columns = [column[1] for column in cursor.fetchall()]

            required_columns = [
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "estimated_cost",
                "cost_breakdown",
                "token_error",
            ]

            missing_columns = [col for col in required_columns if col not in columns]
            if missing_columns:
                print(f"✗ Missing columns in extractions table: {missing_columns}")
                return False
            else:
                print("✓ All required columns present in extractions table")

            # Check token_usage table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'")
            if not cursor.fetchone():
                print("✗ token_usage table not found")
                return False
            else:
                print("✓ token_usage table exists")

            # Check token_usage table structure
            cursor.execute("PRAGMA table_info(token_usage)")
            token_columns = [column[1] for column in cursor.fetchall()]

            required_token_columns = [
                "extraction_id",
                "model_name",
                "prompt_token_count",
                "candidates_token_count",
                "total_cost",
            ]

            missing_token_columns = [col for col in required_token_columns if col not in token_columns]
            if missing_token_columns:
                print(f"✗ Missing columns in token_usage table: {missing_token_columns}")
                return False
            else:
                print("✓ All required columns present in token_usage table")

        print("✓ Migration verification successful!")
        return True

    except Exception as e:
        print(f"✗ Migration verification failed: {e}")
        return False


def backup_database():
    """Create a backup of the database before migration"""

    import shutil
    from datetime import datetime

    db_path = storage_service.db_path
    if not db_path.exists():
        print("No existing database found - skipping backup")
        return True

    backup_path = db_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

    try:
        shutil.copy2(db_path, backup_path)
        print(f"✓ Database backed up to: {backup_path}")
        return True
    except Exception as e:
        print(f"✗ Failed to backup database: {e}")
        return False


def main():
    """Main migration function"""

    print("=== Insurance PDF Extractor Database Migration ===")
    print("Adding token usage tracking to existing database\n")

    # Create backup
    if not backup_database():
        print("Backup failed - aborting migration")
        return 1

    # Run migration
    if not migrate_database():
        print("Migration failed")
        return 1

    # Verify migration
    if not verify_migration():
        print("Migration verification failed")
        return 1

    print("\n🎉 Database migration completed successfully!")
    print("\nYou can now:")
    print("1. Start making API calls with include_token_usage=true")
    print("2. Use the new analytics endpoints to view token usage statistics")
    print("3. Access detailed cost breakdowns and trends")

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
