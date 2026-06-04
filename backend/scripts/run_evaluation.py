#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.services.evaluator import run_evaluation


def print_comparison_table(results: dict) -> None:
    """
    Format and print side-by-side comparison tables.
    """
    print("\n" + "=" * 90)
    print(f" EVALUATION REPORT (Split: {results.get('split', 'unknown')})")
    print(f" Run ID: {results['run_id']} | Timestamp: {results['run_timestamp']}")
    print(f" Prompt: {results['prompt_version']} | Schema: {results['schema_version']}")
    print("=" * 90)

    # 1. Field Averages Table
    print("\nFIELD METRICS SUMMARY:")
    print("-" * 65)
    print(f"{'Field':<20} | {'Precision':<12} | {'Recall':<12} | {'F1 Score':<12}")
    print("-" * 65)
    for field, metrics in results["field_metrics"].items():
        print(f"{field:<20} | {metrics['precision']:<12.4f} | {metrics['recall']:<12.4f} | {metrics['f1']:<12.4f}")
    print("-" * 65)

    # 2. Overall Performance
    print(f"\nOVERALL PERFORMANCE:")
    print(f"Overall Precision : {results['overall_metrics']['precision']:.4f}")
    print(f"Overall Recall    : {results['overall_metrics']['recall']:.4f}")
    print(f"Overall F1        : {results['overall_metrics']['f1']:.4f} (Accuracy)")
    print(f"Regression Flagged: {results['accuracy_regression']}")
    print("-" * 65)

    # 3. Side-by-side detail comparison
    print("\nDETAILED SAMPLE DIFFS:")
    for diff in results["detailed_diffs"]:
        eval_id = diff["eval_id"]
        exp = diff["expected"]
        act = diff["actual"] or {}
        error = diff.get("extraction_error")

        print(f"\nPosting {eval_id}:")
        if error:
            print(f"  [ERROR]: Extraction failed -> {error}")
            continue

        print("-" * 80)
        print(f"  {'Field':<15} | {'Expected':<30} | {'Actual':<30} | Match")
        print("-" * 80)
        for field in ["skills", "tech_stack", "seniority", "remote_policy", "role_archetype", "salary_band"]:
            exp_val = str(exp.get(field))
            act_val = str(act.get(field))
            match_status = "MATCH" if diff["matching_status"].get(field) else "MISMATCH"

            # Truncate strings for formatting
            if len(exp_val) > 28:
                exp_val = exp_val[:25] + "..."
            if len(act_val) > 28:
                act_val = act_val[:25] + "..."

            print(f"  {field:<15} | {exp_val:<30} | {act_val:<30} | {match_status}")
        print("-" * 80)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run LLM signal extraction accuracy evaluation against ground-truth.")
    parser.add_argument("--split", type=str, default="held_out", choices=["train", "held_out"], help="Split to evaluate.")
    parser.add_argument("--prompt-version", type=str, default="extraction_v1", help="Prompt template version filename.")
    parser.add_argument("--dry-run", action="store_true", help="Skips calling Hermes and uses mock data.")
    parser.add_argument("--perturb-dry-run", action="store_true", help="Perturbs dry run mock outputs to test regression.")
    args = parser.parse_args()

    pool = AsyncConnectionPool(conninfo=settings.database_url, open=False)
    await pool.open()

    try:
        async with pool.connection() as conn:
            results = await run_evaluation(
                conn=conn,
                split=args.split,
                prompt_version=args.prompt_version,
                dry_run=args.dry_run,
                perturb_dry_run=args.perturb_dry_run,
            )

        # Print tables
        print_comparison_table(results)

        if results.get("summary_path"):
            print(f"\nWritten evaluation summary artifact to: {results['summary_path']}")

        # Check for regression to determine exit code
        if results["accuracy_regression"]:
            print("\nREGRESSION DETECTED: Overall F1 dropped > 3 percentage points!")
            return 2

    except Exception as exc:
        print(f"\nERROR running evaluation: {exc}")
        return 1
    finally:
        await pool.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
