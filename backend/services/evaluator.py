from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from psycopg.rows import dict_row

from backend.llm.client import (
    JobForExtraction,
    _post_to_hermes,
    _validate_response_items,
)
from backend.llm.hermes import check_hermes_proxy_health
from backend.llm.schemas import (
    EXTRACTION_SCHEMA_VERSION,
    ExtractionBatch,
    ExtractedJobSignal,
    SalaryBand,
)

logger = structlog.get_logger()
DEFAULT_SUMMARY_DIR = Path(__file__).resolve().parents[2] / "_bmad-output" / "implementation-artifacts"
EVAL_FIELDS = ["skills", "tech_stack", "seniority", "remote_policy", "role_archetype", "salary_band"]


def calculate_list_metrics(expected: list[str], actual: list[str]) -> tuple[float, float, float]:
    """
    Calculate Precision, Recall, and F1 score for lists (e.g. skills, tech_stack).
    """
    E = {s.strip().lower() for s in expected if s.strip()}
    A = {s.strip().lower() for s in actual if s.strip()}
    if not E and not A:
        return 1.0, 1.0, 1.0
    if not E or not A:
        return 0.0, 0.0, 0.0
    intersection = E & A
    precision = len(intersection) / len(A)
    recall = len(intersection) / len(E)
    if precision + recall == 0.0:
        return 0.0, 0.0, 0.0
    f1 = 2.0 * (precision * recall) / (precision + recall)
    return precision, recall, f1


def compare_categorical(expected: str, actual: str) -> float:
    """
    Compare categorical enums. Returns 1.0 if match, else 0.0.
    """
    e_clean = (expected or "").strip().lower()
    a_clean = (actual or "").strip().lower()
    return 1.0 if e_clean == a_clean else 0.0


def compare_salary_band(expected: dict | SalaryBand, actual: dict | SalaryBand) -> float:
    """
    Compare salary band structure. Returns 1.0 if identical shape and values, else 0.0.
    """
    e_dict = expected.model_dump() if isinstance(expected, SalaryBand) else expected
    a_dict = actual.model_dump() if isinstance(actual, SalaryBand) else actual

    e_kind = e_dict.get("kind")
    a_kind = a_dict.get("kind")
    if e_kind != a_kind:
        return 0.0
    if e_kind == "not_disclosed":
        return 1.0

    e_curr = (e_dict.get("currency") or "").strip().upper()
    a_curr = (a_dict.get("currency") or "").strip().upper()
    if e_curr != a_curr:
        return 0.0

    if e_dict.get("min_amount") != a_dict.get("min_amount"):
        return 0.0

    if e_dict.get("max_amount") != a_dict.get("max_amount"):
        return 0.0

    e_per = (e_dict.get("period") or "").strip().lower()
    a_per = (a_dict.get("period") or "").strip().lower()
    if e_per != a_per:
        return 0.0

    return 1.0


def load_eval_prompt(prompt_version: str) -> str:
    """
    Load specific prompt version template and replace schema placeholder.
    """
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / f"{prompt_version}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template file not found: {prompt_path}")
    template = prompt_path.read_text(encoding="utf-8")
    schema_json = json.dumps(ExtractionBatch.model_json_schema(), indent=2, sort_keys=True)
    return template.replace("{json_schema}", schema_json)


def write_run_summary(results: dict[str, Any], summary_dir: Path = DEFAULT_SUMMARY_DIR) -> Path:
    run_timestamp = datetime.fromisoformat(results["run_timestamp"])
    year, week, _ = run_timestamp.isocalendar()
    summary_path = summary_dir / f"run-summary-{year}-{week:02d}.json"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    return summary_path


async def run_evaluation(
    conn,
    split: str = "held_out",
    prompt_version: str = "extraction_v1",
    dry_run: bool = False,
    perturb_dry_run: bool = False,
    summary_dir: Path | None = DEFAULT_SUMMARY_DIR,
) -> dict[str, Any]:
    """
    Load ground-truth postings, perform extraction (mocked if dry_run),
    compute field-level and overall F1 scores, check for regression, and log to DB.
    """
    logger.info("Starting evaluation run", split=split, prompt_version=prompt_version, dry_run=dry_run)

    # 1. Hermes Proxy Health Check
    if not dry_run:
        await check_hermes_proxy_health()

    # 2. Load ground-truth postings
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT eval_id, split, job_url, source_slug, title, company, raw_text_excerpt,
                   expected_skills, expected_seniority, expected_tech_stack, expected_salary_band,
                   expected_remote_policy, expected_role_archetype, annotation_notes
            FROM eval_postings
            WHERE split = %s
            ORDER BY eval_id ASC
            """,
            (split,),
        )
        postings = await cur.fetchall()

    if not postings:
        raise ValueError(f"No ground-truth postings found in split: {split}")

    run_timestamp = datetime.now(timezone.utc)
    schema_version = EXTRACTION_SCHEMA_VERSION

    # 3. Perform extraction and compute metrics per sample
    sample_results = []
    for idx, posting in enumerate(postings, start=1):
        eval_id = posting["eval_id"]
        excerpt = posting["raw_text_excerpt"]

        expected_obj = {
            "skills": posting["expected_skills"],
            "seniority": posting["expected_seniority"],
            "tech_stack": posting["expected_tech_stack"],
            "salary_band": posting["expected_salary_band"],
            "remote_policy": posting["expected_remote_policy"],
            "role_archetype": posting["expected_role_archetype"],
        }

        actual_obj = None
        extraction_error = None

        if dry_run:
            # Mock extraction matching ground truth
            skills_mock = list(posting["expected_skills"])
            seniority_mock = posting["expected_seniority"]
            tech_stack_mock = list(posting["expected_tech_stack"])
            salary_band_mock = SalaryBand.model_validate(posting["expected_salary_band"])
            remote_policy_mock = posting["expected_remote_policy"]
            role_archetype_mock = posting["expected_role_archetype"]

            if perturb_dry_run:
                # Perturb the first sample
                if idx == 1:
                    if skills_mock:
                        skills_mock = skills_mock[1:]
                    else:
                        skills_mock = ["MockedSkill"]
                    remote_policy_mock = "unknown"

            actual_obj = ExtractedJobSignal(
                job_id=idx,
                skills=skills_mock,
                seniority=seniority_mock,
                tech_stack=tech_stack_mock,
                salary_band=salary_band_mock,
                remote_policy=remote_policy_mock,
                role_archetype=role_archetype_mock,
            )
        else:
            try:
                prompt = load_eval_prompt(prompt_version)
                job = JobForExtraction(
                    id=idx,
                    url=posting["job_url"],
                    title=posting["title"],
                    company=posting["company"],
                    location=None,
                    raw_text=excerpt,
                    source_slug=posting["source_slug"],
                )
                response_payload = await _post_to_hermes([job], prompt, prompt_version=prompt_version)
                valid_by_id, item_errors = _validate_response_items(response_payload, {idx})

                if idx in valid_by_id:
                    actual_obj = valid_by_id[idx]
                elif idx in item_errors:
                    extraction_error = item_errors[idx]
                else:
                    extraction_error = "Missing extraction result in proxy response"
            except Exception as exc:
                extraction_error = str(exc)
                logger.warning("Extraction failed for posting during evaluation", eval_id=eval_id, error=extraction_error)

        metrics = {}
        if actual_obj is not None:
            # Skills
            p_sk, r_sk, f1_sk = calculate_list_metrics(expected_obj["skills"], actual_obj.skills)
            metrics["skills"] = {"precision": p_sk, "recall": r_sk, "f1": f1_sk}

            # Tech Stack
            p_ts, r_ts, f1_ts = calculate_list_metrics(expected_obj["tech_stack"], actual_obj.tech_stack)
            metrics["tech_stack"] = {"precision": p_ts, "recall": r_ts, "f1": f1_ts}

            # Seniority
            f1_sn = compare_categorical(expected_obj["seniority"], actual_obj.seniority)
            metrics["seniority"] = {"precision": f1_sn, "recall": f1_sn, "f1": f1_sn}

            # Remote Policy
            f1_rp = compare_categorical(expected_obj["remote_policy"], actual_obj.remote_policy)
            metrics["remote_policy"] = {"precision": f1_rp, "recall": f1_rp, "f1": f1_rp}

            # Role Archetype
            f1_ra = compare_categorical(expected_obj["role_archetype"], actual_obj.role_archetype)
            metrics["role_archetype"] = {"precision": f1_ra, "recall": f1_ra, "f1": f1_ra}

            # Salary Band
            f1_sb = compare_salary_band(expected_obj["salary_band"], actual_obj.salary_band)
            metrics["salary_band"] = {"precision": f1_sb, "recall": f1_sb, "f1": f1_sb}

            actual_dump = actual_obj.model_dump()
        else:
            for field in EVAL_FIELDS:
                metrics[field] = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
            actual_dump = None

        sample_f1 = sum(metrics[f]["f1"] for f in metrics) / 6.0
        mismatches = [f for f in metrics if metrics[f]["f1"] < 1.0]
        matching_status = {f: (metrics[f]["f1"] == 1.0) for f in metrics}

        sample_results.append({
            "eval_id": eval_id,
            "expected": expected_obj,
            "actual": actual_dump,
            "metrics": metrics,
            "overall_f1": sample_f1,
            "mismatches": mismatches,
            "matching_status": matching_status,
            "extraction_error": extraction_error,
        })

    # 4. Compute averaged metrics across all postings
    num_samples = len(sample_results)
    field_averages = {}
    for field in EVAL_FIELDS:
        avg_precision = sum(r["metrics"][field]["precision"] for r in sample_results) / num_samples
        avg_recall = sum(r["metrics"][field]["recall"] for r in sample_results) / num_samples
        avg_f1 = sum(r["metrics"][field]["f1"] for r in sample_results) / num_samples
        field_averages[field] = {
            "precision": round(avg_precision, 4),
            "recall": round(avg_recall, 4),
            "f1": round(avg_f1, 4),
        }

    overall_f1 = sum(field_averages[f]["f1"] for f in field_averages) / 6.0
    overall_precision = sum(field_averages[f]["precision"] for f in field_averages) / 6.0
    overall_recall = sum(field_averages[f]["recall"] for f in field_averages) / 6.0

    overall_f1 = round(overall_f1, 4)
    overall_precision = round(overall_precision, 4)
    overall_recall = round(overall_recall, 4)
    overall_accuracy = overall_f1

    # 5. Regression Detection
    prior_f1 = None
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT overall_f1
            FROM evaluation_runs
            ORDER BY run_timestamp DESC, id DESC
            LIMIT 1
            """
        )
        last_run = await cur.fetchone()
        if last_run:
            prior_f1 = float(last_run["overall_f1"])

    accuracy_regression = False
    if prior_f1 is not None:
        delta = prior_f1 - overall_f1
        if delta > 0.03:
            accuracy_regression = True

    metrics_json = {
        "field_metrics": field_averages,
        "num_samples": num_samples,
        "prior_f1": prior_f1,
        "split": split,
    }

    # 6. Save execution run
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO evaluation_runs (
                run_timestamp, prompt_version, extraction_schema_version,
                overall_accuracy, overall_precision, overall_recall, overall_f1,
                accuracy_regression, metrics
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                run_timestamp,
                prompt_version,
                schema_version,
                overall_accuracy,
                overall_precision,
                overall_recall,
                overall_f1,
                accuracy_regression,
                json.dumps(metrics_json),
            ),
        )
        run_id_db = (await cur.fetchone())[0]

    logger.info(
        "Finished evaluation run and saved results",
        run_id=run_id_db,
        overall_f1=overall_f1,
        regression=accuracy_regression,
    )

    results = {
        "run_id": run_id_db,
        "run_timestamp": run_timestamp.isoformat(),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "split": split,
        "overall_metrics": {
            "precision": overall_precision,
            "recall": overall_recall,
            "f1": overall_f1,
        },
        "accuracy_regression": accuracy_regression,
        "field_metrics": field_averages,
        "detailed_diffs": [
            {
                "eval_id": r["eval_id"],
                "expected": r["expected"],
                "actual": r["actual"],
                "matching_status": r["matching_status"],
                "mismatched_fields": r["mismatches"],
                "metrics": r["metrics"],
                "overall_f1": r["overall_f1"],
                "extraction_error": r["extraction_error"],
            }
            for r in sample_results
        ],
    }
    if summary_dir is not None:
        results["summary_path"] = str(write_run_summary(results, summary_dir))

    return results
