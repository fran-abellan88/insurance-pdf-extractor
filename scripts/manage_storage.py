"""
CLI tool for managing stored extraction data
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.storage import storage_service


def show_stats():
    """Show storage statistics"""
    stats = storage_service.get_field_statistics()

    print("=== Storage Statistics ===")
    print(f"Total extractions: {stats.get('total_extractions', 0)}")
    print(f"Database path: {storage_service.db_path}")

    if stats.get("status_breakdown"):
        print("\nStatus Breakdown:")
        for status_info in stats["status_breakdown"]:
            print(f"  {status_info['status']}: {status_info['count']} ({status_info['percentage']}%)")

    if stats.get("field_success_rates"):
        print("\nTop 10 Field Success Rates:")
        for field_info in stats["field_success_rates"][:10]:
            print(
                f"  {field_info['field_name']}: {field_info['success_rate']}% "
                f"({field_info['successful']}/{field_info['total_occurrences']})"
            )


def list_recent(limit=10):
    """List recent extractions"""
    extractions = storage_service.get_recent_extractions(limit=limit)

    print(f"=== Recent {limit} Extractions ===")
    print(f"{'ID':<5} {'Filename':<30} {'Status':<15} {'Model':<20} {'Date':<20}")
    print("-" * 90)

    for extraction in extractions:
        print(
            f"{extraction['id']:<5} "
            f"{extraction['filename'][:29]:<30} "
            f"{extraction['status']:<15} "
            f"{extraction['model_used']:<20} "
            f"{extraction['created_at'][:19]:<20}"
        )


def cleanup_old(days_to_keep=90, dry_run=False):
    """Clean up old records"""
    if dry_run:
        print(f"DRY RUN: Would clean up records older than {days_to_keep} days")
        # You could implement a count-only version here
        return

    deleted_count = storage_service.cleanup_old_records(days_to_keep)
    print(f"Cleaned up {deleted_count} records older than {days_to_keep} days")


def export_data(format_type="json", output_file=None):
    """Export all data"""
    extractions = storage_service.get_recent_extractions(limit=10000)

    if not output_file:
        output_file = f"extractions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

    if format_type == "json":
        import json

        with open(output_file, "w") as f:
            json.dump(
                {
                    "extractions": extractions,
                    "export_date": datetime.now().isoformat(),
                    "total_records": len(extractions),
                },
                f,
                indent=2,
            )

    elif format_type == "csv":
        import csv

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

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for extraction in extractions:
                row = {field: extraction.get(field, "") for field in fieldnames}
                writer.writerow(row)

    print(f"Exported {len(extractions)} records to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Manage stored extraction data")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Stats command
    subparsers.add_parser("stats", help="Show storage statistics")

    # List command
    list_parser = subparsers.add_parser("list", help="List recent extractions")
    list_parser.add_argument("--limit", type=int, default=10, help="Number of records to show")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old records")
    cleanup_parser.add_argument("--days", type=int, default=90, help="Days to keep")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    export_parser.add_argument("--output", help="Output filename")

    args = parser.parse_args()

    if args.command == "stats":
        show_stats()
    elif args.command == "list":
        list_recent(args.limit)
    elif args.command == "cleanup":
        cleanup_old(args.days, args.dry_run)
    elif args.command == "export":
        export_data(args.format, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
