#!/usr/bin/env python3
"""
CLI tool for viewing token usage analytics
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.storage import storage_service


def show_token_overview():
    """Show token usage overview"""
    stats = storage_service.get_token_usage_statistics()

    if not stats or not stats.get("overall_statistics"):
        print("No token usage data available.")
        return

    overall = stats["overall_statistics"]

    print("=== Token Usage Overview ===")
    print(f"Total extractions with token data: {overall.get('total_extractions_with_tokens', 0)}")
    print(f"Total input tokens: {overall.get('total_input_tokens', 0):,}")
    print(f"Total output tokens: {overall.get('total_output_tokens', 0):,}")
    print(f"Total tokens used: {overall.get('total_tokens_used', 0):,}")
    print(f"Total estimated cost: ${overall.get('total_estimated_cost', 0):.6f}")
    print(f"Average cost per extraction: ${overall.get('avg_cost_per_extraction', 0):.6f}")
    print(f"Min cost: ${overall.get('min_cost', 0):.6f}")
    print(f"Max cost: ${overall.get('max_cost', 0):.6f}")


def show_model_breakdown():
    """Show token usage by model"""
    stats = storage_service.get_token_usage_statistics()
    model_stats = stats.get("statistics_by_model", [])

    if not model_stats:
        print("No model statistics available.")
        return

    print("\n=== Token Usage by Model ===")
    print(f"{'Model':<25} {'Extractions':<12} {'Total Cost':<12} {'Avg Cost':<12} {'Total Tokens':<15}")
    print("-" * 80)

    for model in model_stats:
        total_tokens = model.get("total_input_tokens", 0) + model.get("total_output_tokens", 0)
        print(
            f"{model['model_used']:<25} "
            f"{model['extraction_count']:<12} "
            f"${model['total_cost']:<11.6f} "
            f"${model['avg_cost']:<11.6f} "
            f"{total_tokens:<15,}"
        )


def show_expensive_extractions(limit=10):
    """Show most expensive extractions"""
    stats = storage_service.get_token_usage_statistics()
    expensive = stats.get("most_expensive_extractions", [])

    if not expensive:
        print("No expensive extractions data available.")
        return

    print(f"\n=== Top {limit} Most Expensive Extractions ===")
    print(f"{'ID':<5} {'Filename':<30} {'Model':<20} {'Cost':<12} {'Tokens':<10} {'Date':<12}")
    print("-" * 95)

    for extraction in expensive[:limit]:
        total_tokens = extraction.get("input_tokens", 0) + extraction.get("output_tokens", 0)
        date_str = extraction.get("created_at", "")[:10] if extraction.get("created_at") else "Unknown"
        filename = extraction.get("filename", "Unknown")[:29]

        print(
            f"{extraction.get('id', 0):<5} "
            f"{filename:<30} "
            f"{extraction.get('model_used', 'Unknown'):<20} "
            f"${extraction.get('estimated_cost', 0):<11.6f} "
            f"{total_tokens:<10,} "
            f"{date_str:<12}"
        )


def show_daily_trends(days=7):
    """Show daily cost trends"""
    stats = storage_service.get_token_usage_statistics()
    trends = stats.get("daily_cost_trends", [])

    if not trends:
        print("No daily trends data available.")
        return

    print(f"\n=== Daily Cost Trends (Last {days} days) ===")
    print(f"{'Date':<12} {'Extractions':<12} {'Daily Cost':<12} {'Daily Tokens':<15}")
    print("-" * 55)

    for trend in trends[:days]:
        print(
            f"{trend['date']:<12} "
            f"{trend['extraction_count']:<12} "
            f"${trend['daily_cost']:<11.6f} "
            f"{trend['daily_tokens']:<15,}"
        )


def predict_costs(extractions_count, model_name=None):
    """Predict costs for planned extractions"""
    stats = storage_service.get_token_usage_statistics()

    if model_name:
        model_stats = [s for s in stats.get("statistics_by_model", []) if s["model_used"] == model_name]
        if not model_stats:
            print(f"No data found for model: {model_name}")
            return
        avg_cost = model_stats[0]["avg_cost"]
        model_used = model_name
    else:
        overall = stats.get("overall_statistics", {})
        avg_cost = overall.get("avg_cost_per_extraction", 0)
        model_used = "all models"

    if not avg_cost:
        print("Insufficient data for cost prediction.")
        return

    total_cost = extractions_count * avg_cost
    cost_low = total_cost * 0.8
    cost_high = total_cost * 1.2

    print("\n=== Cost Prediction ===")
    print(f"Planned extractions: {extractions_count}")
    print(f"Based on: {model_used}")
    print(f"Average cost per extraction: ${avg_cost:.6f}")
    print(f"Estimated total cost: ${total_cost:.6f}")
    print(f"Cost range (±20%): ${cost_low:.6f} - ${cost_high:.6f}")


def export_data(format_type="json", output_file=None):
    """Export token usage data"""
    stats = storage_service.get_token_usage_statistics()

    if not output_file:
        output_file = f"token_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

    if format_type == "json":
        with open(output_file, "w") as f:
            json.dump({"export_date": datetime.now().isoformat(), "token_analytics": stats}, f, indent=2)

    elif format_type == "csv":
        import csv

        with open(output_file, "w", newline="") as f:
            if stats.get("statistics_by_model"):
                fieldnames = [
                    "model_used",
                    "extraction_count",
                    "total_input_tokens",
                    "total_output_tokens",
                    "total_cost",
                    "avg_cost",
                ]

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for model_stat in stats["statistics_by_model"]:
                    writer.writerow({field: model_stat.get(field, "") for field in fieldnames})

    print(f"Token analytics exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Token Usage Analytics CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Overview command
    subparsers.add_parser("overview", help="Show token usage overview")

    # Models command
    subparsers.add_parser("models", help="Show token usage breakdown by model")

    # Expensive command
    expensive_parser = subparsers.add_parser("expensive", help="Show most expensive extractions")
    expensive_parser.add_argument("--limit", type=int, default=10, help="Number of records to show")

    # Trends command
    trends_parser = subparsers.add_parser("trends", help="Show daily cost trends")
    trends_parser.add_argument("--days", type=int, default=7, help="Number of days to show")

    # Predict command
    predict_parser = subparsers.add_parser("predict", help="Predict costs for planned extractions")
    predict_parser.add_argument("count", type=int, help="Number of planned extractions")
    predict_parser.add_argument("--model", help="Specific model to use for prediction")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export token usage data")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    export_parser.add_argument("--output", help="Output filename")

    # Summary command
    subparsers.add_parser("summary", help="Show comprehensive summary")

    args = parser.parse_args()

    if args.command == "overview":
        show_token_overview()
    elif args.command == "models":
        show_model_breakdown()
    elif args.command == "expensive":
        show_expensive_extractions(args.limit)
    elif args.command == "trends":
        show_daily_trends(args.days)
    elif args.command == "predict":
        predict_costs(args.count, args.model)
    elif args.command == "export":
        export_data(args.format, args.output)
    elif args.command == "summary":
        show_token_overview()
        show_model_breakdown()
        show_expensive_extractions(5)
        show_daily_trends(7)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
