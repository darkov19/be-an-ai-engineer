from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import psycopg
from psycopg.rows import dict_row
import structlog

router = APIRouter()
logger = structlog.get_logger()

INDIA_SEGMENT_SQL = """
CASE
    WHEN (
        lower(coalesce(location, '')) LIKE ANY (ARRAY[
            '%india%', '%bengaluru%', '%bangalore%', '%mumbai%', '%pune%',
            '%gurgaon%', '%gurugram%', '%noida%', '%hyderabad%', '%chennai%',
            '%delhi%', '%bhopal%'
        ])
        OR lower(coalesce(company, '')) = ANY (ARRAY[
            'sarvam ai', 'krutrim', 'yellow.ai', 'haptik', 'qure.ai', 'gnani.ai',
            'ideaforge', 'peak', 'observe.ai', 'fractal', 'microsoft india ai',
            'google india', 'amazon india', 'nvidia india', 'adobe india'
        ])
    ) THEN 'india_ai_product'
    WHEN lower(coalesce(remote_policy, '')) = 'remote' THEN 'us_eu_remote'
    ELSE 'unclassified'
END
"""

SEGMENTED_JOBS_CTE = f"""
WITH segmented_jobs AS (
    SELECT
        id,
        {INDIA_SEGMENT_SQL} AS segment,
        skills,
        tech_stack,
        seniority,
        salary_band
    FROM jobs
    WHERE extraction_status = 'extracted'
)
"""


def _as_float(value):
    return float(value) if value is not None else 0.0


def _profile_skill_set(skills_field):
    if not isinstance(skills_field, list):
        return set()
    return {
        skill.strip().lower()
        for skill in skills_field
        if isinstance(skill, str) and skill.strip()
    }


def _historical_fit_score(prior_report_row, segment, candidate_profile_skills):
    if not prior_report_row:
        return None

    key = "geo_us_eu" if segment == "us_eu_remote" else "geo_india"
    prior_payload = prior_report_row.get(key) if isinstance(prior_report_row, dict) else None
    if not isinstance(prior_payload, dict):
        return None

    prior_skills = prior_payload.get("top_skills")
    if not isinstance(prior_skills, list):
        return None

    prior_skill_names = set()
    for item in prior_skills:
        if not isinstance(item, dict):
            continue
        skill = item.get("skill")
        if isinstance(skill, str) and skill.strip():
            prior_skill_names.add(skill.strip().lower())

    return len(candidate_profile_skills.intersection(prior_skill_names)) / 30.0


async def _get_system_metadata(cur):
    await cur.execute("SELECT COUNT(*) FROM jobs")
    row = await cur.fetchone()
    corpus_size = int(row["count"]) if row else 0

    await cur.execute("SELECT overall_f1 FROM evaluation_runs ORDER BY run_timestamp DESC, id DESC LIMIT 1")
    row = await cur.fetchone()
    eval_accuracy = None
    if row and row["overall_f1"] is not None:
        eval_accuracy = float(row["overall_f1"])

    await cur.execute("SELECT status FROM ingestion_runs ORDER BY run_timestamp DESC, id DESC LIMIT 1")
    row = await cur.fetchone()
    latest_ingest_status = row["status"] if row else None

    check_accuracy = eval_accuracy if eval_accuracy is not None else 1.0
    corpus_breached = corpus_size < 100
    accuracy_breached = check_accuracy < 0.70
    latest_ingest_succeeded = latest_ingest_status == "success"

    if (
        corpus_size == 0
        or not latest_ingest_succeeded
        or (corpus_breached and accuracy_breached)
    ):
        system_state = "locked"
    elif corpus_breached != accuracy_breached:
        system_state = "warning"
    else:
        system_state = "nominal"

    return corpus_size, eval_accuracy, system_state


async def _get_extracted_count(cur):
    await cur.execute("SELECT COUNT(*) FROM jobs WHERE extraction_status = 'extracted'")
    row = await cur.fetchone()
    return int(row["count"]) if row else 0


async def _get_segment_counts(cur):
    await cur.execute(
        f"""
        {SEGMENTED_JOBS_CTE}
        SELECT segment, COUNT(*)::int AS job_count
        FROM segmented_jobs
        GROUP BY segment
        """
    )
    return {row["segment"]: int(row["job_count"]) for row in await cur.fetchall()}


async def _get_top_skills(cur):
    await cur.execute(
        f"""
        {SEGMENTED_JOBS_CTE},
        skill_job_rows AS (
            SELECT
                segmented_jobs.id,
                segmented_jobs.segment,
                lower(btrim(skill_value)) AS skill_key,
                min(btrim(skill_value)) AS skill_label
            FROM segmented_jobs
            CROSS JOIN LATERAL jsonb_array_elements_text(
                CASE
                    WHEN jsonb_typeof(segmented_jobs.skills) = 'array' THEN segmented_jobs.skills
                    ELSE '[]'::jsonb
                END
            ) AS skill_value
            WHERE btrim(skill_value) <> ''
                AND lower(btrim(skill_value)) <> 'unknown'
            GROUP BY segmented_jobs.id, segmented_jobs.segment, lower(btrim(skill_value))
        ),
        denominators AS (
            SELECT segment, COUNT(DISTINCT id)::float AS valid_job_count
            FROM skill_job_rows
            GROUP BY segment
        ),
        ranked AS (
            SELECT
                skill_job_rows.segment,
                skill_job_rows.skill_key,
                min(skill_job_rows.skill_label) AS skill,
                COUNT(*)::int AS skill_count,
                COUNT(*)::float / NULLIF(denominators.valid_job_count, 0) AS frequency,
                row_number() OVER (
                    PARTITION BY skill_job_rows.segment
                    ORDER BY COUNT(*) DESC, skill_job_rows.skill_key
                ) AS rank
            FROM skill_job_rows
            JOIN denominators ON denominators.segment = skill_job_rows.segment
            GROUP BY skill_job_rows.segment, skill_job_rows.skill_key, denominators.valid_job_count
        )
        SELECT segment, skill_key, skill, skill_count, frequency
        FROM ranked
        WHERE rank <= 30
        ORDER BY segment, skill_count DESC, skill_key
        """
    )
    top_skills = {"us_eu_remote": [], "india_ai_product": []}
    top_skill_keys = {"us_eu_remote": set(), "india_ai_product": set()}
    for row in await cur.fetchall():
        segment = row["segment"]
        if segment not in top_skills:
            continue
        top_skill_keys[segment].add(row["skill_key"])
        top_skills[segment].append(
            {
                "skill": row["skill"],
                "count": int(row["skill_count"]),
                "frequency": _as_float(row["frequency"]),
            }
        )
    return top_skills, top_skill_keys


async def _get_co_occurrences(cur):
    await cur.execute(
        f"""
        {SEGMENTED_JOBS_CTE},
        skill_job_rows AS (
            SELECT
                segmented_jobs.id,
                segmented_jobs.segment,
                lower(btrim(skill_value)) AS skill_key,
                min(btrim(skill_value)) AS skill_label
            FROM segmented_jobs
            CROSS JOIN LATERAL jsonb_array_elements_text(
                CASE
                    WHEN jsonb_typeof(segmented_jobs.skills) = 'array' THEN segmented_jobs.skills
                    ELSE '[]'::jsonb
                END
            ) AS skill_value
            WHERE btrim(skill_value) <> ''
                AND lower(btrim(skill_value)) <> 'unknown'
            GROUP BY segmented_jobs.id, segmented_jobs.segment, lower(btrim(skill_value))
        ),
        denominators AS (
            SELECT segment, COUNT(DISTINCT id)::float AS valid_job_count
            FROM skill_job_rows
            GROUP BY segment
        ),
        top_skills AS (
            SELECT segment, skill_key, min(skill_label) AS skill, COUNT(*)::int AS skill_count
            FROM skill_job_rows
            JOIN denominators USING (segment)
            GROUP BY segment, skill_key
            ORDER BY segment, COUNT(*) DESC, skill_key
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY segment ORDER BY skill_count DESC, skill_key) AS rank
            FROM top_skills
        )
        SELECT
            a.segment,
            a.skill AS skill_a,
            b.skill AS skill_b,
            COUNT(*)::int AS co_occur_count,
            COUNT(*)::float / NULLIF(a.skill_count, 0) AS probability
        FROM ranked a
        JOIN ranked b
            ON b.segment = a.segment
            AND b.skill_key <> a.skill_key
            AND b.rank <= 30
        JOIN skill_job_rows row_a
            ON row_a.segment = a.segment
            AND row_a.skill_key = a.skill_key
        JOIN skill_job_rows row_b
            ON row_b.segment = b.segment
            AND row_b.skill_key = b.skill_key
            AND row_b.id = row_a.id
        WHERE a.rank <= 30
        GROUP BY a.segment, a.skill_key, a.skill, a.skill_count, b.skill_key, b.skill
        ORDER BY a.segment, co_occur_count DESC, lower(a.skill), lower(b.skill)
        """
    )
    co_occurrences = {"us_eu_remote": [], "india_ai_product": []}
    for row in await cur.fetchall():
        segment = row["segment"]
        if segment not in co_occurrences:
            continue
        co_occurrences[segment].append(
            {
                "skill_a": row["skill_a"],
                "skill_b": row["skill_b"],
                "co_occur_count": int(row["co_occur_count"]),
                "probability": _as_float(row["probability"]),
            }
        )
    return co_occurrences


async def _get_salary_correlations(cur):
    await cur.execute(
        f"""
        {SEGMENTED_JOBS_CTE},
        salary_jobs AS (
            SELECT
                id,
                segment,
                (salary_band->>'min_amount')::float AS min_amount,
                (salary_band->>'max_amount')::float AS max_amount,
                salary_band->>'currency' AS currency,
                salary_band->>'period' AS period,
                skills,
                tech_stack
            FROM segmented_jobs
            WHERE jsonb_typeof(salary_band) = 'object'
                AND salary_band->>'kind' = 'disclosed'
                AND salary_band->>'currency' IS NOT NULL
                AND salary_band->>'period' IS NOT NULL
                AND salary_band->>'min_amount' ~ '^[0-9]+(\\.[0-9]+)?$'
                AND salary_band->>'max_amount' ~ '^[0-9]+(\\.[0-9]+)?$'
                AND (salary_band->>'min_amount')::float >= 0
                AND (salary_band->>'max_amount')::float >= (salary_band->>'min_amount')::float
        ),
        item_rows AS (
            SELECT
                salary_jobs.id,
                salary_jobs.segment,
                salary_jobs.min_amount,
                salary_jobs.max_amount,
                salary_jobs.currency,
                salary_jobs.period,
                lower(btrim(item_value)) AS item_key,
                min(btrim(item_value)) AS item_label
            FROM salary_jobs
            CROSS JOIN LATERAL (
                SELECT item_value
                FROM jsonb_array_elements_text(
                    CASE
                        WHEN jsonb_typeof(salary_jobs.skills) = 'array' THEN salary_jobs.skills
                        ELSE '[]'::jsonb
                    END
                ) AS item_value
                UNION ALL
                SELECT item_value
                FROM jsonb_array_elements_text(
                    CASE
                        WHEN jsonb_typeof(salary_jobs.tech_stack) = 'array' THEN salary_jobs.tech_stack
                        ELSE '[]'::jsonb
                    END
                ) AS item_value
            ) items
            WHERE btrim(item_value) <> ''
                AND lower(btrim(item_value)) <> 'unknown'
            GROUP BY
                salary_jobs.id,
                salary_jobs.segment,
                salary_jobs.min_amount,
                salary_jobs.max_amount,
                salary_jobs.currency,
                salary_jobs.period,
                lower(btrim(item_value))
        )
        SELECT
            segment,
            min(item_label) AS skill_or_tech,
            AVG(min_amount) AS avg_min_salary,
            AVG(max_amount) AS avg_max_salary,
            currency,
            period,
            COUNT(*)::int AS disclosed_count
        FROM item_rows
        GROUP BY segment, item_key, currency, period
        ORDER BY segment, disclosed_count DESC, lower(min(item_label))
        """
    )
    salary_correlations = {"us_eu_remote": [], "india_ai_product": []}
    for row in await cur.fetchall():
        segment = row["segment"]
        if segment not in salary_correlations:
            continue
        salary_correlations[segment].append(
            {
                "skill_or_tech": row["skill_or_tech"],
                "avg_min_salary": _as_float(row["avg_min_salary"]),
                "avg_max_salary": _as_float(row["avg_max_salary"]),
                "currency": row["currency"],
                "period": row["period"],
                "disclosed_count": int(row["disclosed_count"]),
            }
        )
    return salary_correlations


async def _get_experience_distribution(cur):
    await cur.execute(
        f"""
        {SEGMENTED_JOBS_CTE}
        SELECT
            segment,
            COUNT(*)::int AS job_count,
            COUNT(*) FILTER (
                WHERE seniority IS NULL
                    OR btrim(seniority) = ''
                    OR lower(btrim(seniority)) IN ('entry', 'unknown')
                    OR lower(btrim(seniority)) NOT IN ('mid', 'senior', 'staff_plus')
            )::int AS no_minimum_count,
            COUNT(*) FILTER (WHERE lower(btrim(seniority)) = 'mid')::int AS three_plus_count,
            COUNT(*) FILTER (WHERE lower(btrim(seniority)) = 'senior')::int AS five_plus_count,
            COUNT(*) FILTER (WHERE lower(btrim(seniority)) = 'staff_plus')::int AS senior_only_count
        FROM segmented_jobs
        WHERE segment IN ('us_eu_remote', 'india_ai_product')
        GROUP BY segment
        """
    )
    distributions = {}
    for row in await cur.fetchall():
        job_count = int(row["job_count"])
        if job_count == 0:
            continue
        distributions[row["segment"]] = {
            "no_minimum": int(row["no_minimum_count"]) / job_count,
            "three_plus": int(row["three_plus_count"]) / job_count,
            "five_plus": int(row["five_plus_count"]) / job_count,
            "senior_only": int(row["senior_only_count"]) / job_count,
        }
    return distributions


async def _get_candidate_profile_skills(cur):
    await cur.execute("SELECT skills FROM profiles WHERE id = 1")
    row = await cur.fetchone()
    return _profile_skill_set(row["skills"] if row else None)


async def _get_prior_report(cur):
    await cur.execute(
        """
        SELECT geo_us_eu, geo_india
        FROM weekly_reports
        WHERE run_date < CURRENT_DATE
        ORDER BY run_date DESC
        LIMIT 1
        """
    )
    return await cur.fetchone()


@router.get("/jobs/analytics")
async def get_jobs_analytics(request: Request):
    try:
        if not hasattr(request.app.state, "pool") or request.app.state.pool is None:
            raise RuntimeError("Database pool not initialized")

        async with request.app.state.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                corpus_size, eval_accuracy, system_state = await _get_system_metadata(cur)

                if system_state == "locked":
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": True,
                            "code": "METRICS_LOCKED",
                            "detail": "Ingestion corpus or accuracy below minimum quality thresholds. Dashboard locked.",
                        },
                    )

                extracted_count = await _get_extracted_count(cur)
                extracted_coverage = extracted_count / corpus_size if corpus_size > 0 else 0.0
                segment_counts = await _get_segment_counts(cur)
                top_skills, top_skill_keys = await _get_top_skills(cur)
                co_occurrences = await _get_co_occurrences(cur)
                salary_correlations = await _get_salary_correlations(cur)
                experience_distribution = await _get_experience_distribution(cur)
                candidate_profile_skills = await _get_candidate_profile_skills(cur)
                prior_report_row = await _get_prior_report(cur)

                geo_segments_payload = {}
                for segment in ("us_eu_remote", "india_ai_product"):
                    segment_top_skills = top_skills.get(segment, [])
                    current_fit_score = len(
                        candidate_profile_skills.intersection(top_skill_keys.get(segment, set()))
                    ) / 30.0
                    prior_fit_score = _historical_fit_score(
                        prior_report_row,
                        segment,
                        candidate_profile_skills,
                    )
                    profile_fit_delta = (
                        0.0 if prior_fit_score is None else current_fit_score - prior_fit_score
                    )

                    skill_gap = [
                        {
                            "skill": skill["skill"],
                            "market_frequency": skill["frequency"],
                            "in_profile": False,
                        }
                        for skill in segment_top_skills
                        if skill["skill"].strip().lower() not in candidate_profile_skills
                    ]

                    geo_segments_payload[segment] = {
                        "job_count": segment_counts.get(segment, 0),
                        "top_skills": segment_top_skills,
                        "co_occurrences": co_occurrences.get(segment, []),
                        "salary_correlations": salary_correlations.get(segment, []),
                        "experience_distribution": experience_distribution.get(
                            segment,
                            {
                                "no_minimum": 0.0,
                                "three_plus": 0.0,
                                "five_plus": 0.0,
                                "senior_only": 0.0,
                            },
                        ),
                        "profile_fit_score": current_fit_score,
                        "profile_fit_delta": profile_fit_delta,
                        "skill_gap": skill_gap,
                    }

                geo_segments_payload["unclassified"] = {
                    "job_count": segment_counts.get("unclassified", 0)
                }

                return {
                    "data": {
                        "corpus_size": corpus_size,
                        "extracted_coverage": extracted_coverage,
                        "latest_eval_accuracy": eval_accuracy,
                        "system_state": system_state,
                        "geo_segments": geo_segments_payload,
                    }
                }

    except Exception as exc:
        logger.error("Failed to compute jobs analytics", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "code": "DB_CONNECTION_ERROR",
                "detail": "Database query execution failure.",
            },
        )
