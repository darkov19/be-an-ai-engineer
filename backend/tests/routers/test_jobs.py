import pytest


class MockCursor:
    def __init__(self, query_results, execute_error=None):
        self.query_results = list(query_results)
        self.execute_error = execute_error
        self.current_result = []
        self.execute_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        self.execute_calls.append((query, vars))
        if self.execute_error:
            raise self.execute_error
        self.current_result = list(self.query_results.pop(0)) if self.query_results else []

    async def fetchone(self):
        if not self.current_result:
            return None
        return self.current_result.pop(0)

    async def fetchall(self):
        result = self.current_result
        self.current_result = []
        return result


class MockConnection:
    def __init__(self, query_results, execute_error=None):
        self.query_results = query_results
        self.execute_error = execute_error
        self.cursors = []

    def cursor(self, *args, **kwargs):
        cur = MockCursor(self.query_results, self.execute_error)
        self.cursors.append(cur)
        return cur


class MockPool:
    def __init__(self, query_results, execute_error=None):
        self.query_results = query_results
        self.execute_error = execute_error
        self.connections = []

    async def __aenter__(self):
        conn = MockConnection(self.query_results, self.execute_error)
        self.connections.append(conn)
        return conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def connection(self):
        return self


def analytics_query_results(
    *,
    corpus_size=150,
    eval_accuracy=0.85,
    ingest_status="success",
    extracted_count=4,
    segment_counts=None,
    top_skills=None,
    co_occurrences=None,
    salary_correlations=None,
    experience_distribution=None,
    profile_skills=None,
    prior_report=None,
):
    return [
        [{"count": corpus_size}],
        [{"overall_f1": eval_accuracy}],
        [{"status": ingest_status}],
        [{"count": extracted_count}],
        segment_counts
        or [
            {"segment": "india_ai_product", "job_count": 1},
            {"segment": "us_eu_remote", "job_count": 2},
            {"segment": "unclassified", "job_count": 1},
        ],
        top_skills
        or [
            {
                "segment": "india_ai_product",
                "skill_key": "python",
                "skill": "Python",
                "skill_count": 1,
                "frequency": 1.0,
            },
            {
                "segment": "india_ai_product",
                "skill_key": "react",
                "skill": "React",
                "skill_count": 1,
                "frequency": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_key": "pgvector",
                "skill": "pgvector",
                "skill_count": 2,
                "frequency": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_key": "python",
                "skill": "Python",
                "skill_count": 2,
                "frequency": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_key": "rag",
                "skill": "RAG",
                "skill_count": 2,
                "frequency": 1.0,
            },
        ],
        co_occurrences
        or [
            {
                "segment": "us_eu_remote",
                "skill_a": "pgvector",
                "skill_b": "Python",
                "co_occur_count": 2,
                "probability": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_a": "pgvector",
                "skill_b": "RAG",
                "co_occur_count": 2,
                "probability": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_a": "Python",
                "skill_b": "pgvector",
                "co_occur_count": 2,
                "probability": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_a": "Python",
                "skill_b": "RAG",
                "co_occur_count": 2,
                "probability": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_a": "RAG",
                "skill_b": "pgvector",
                "co_occur_count": 2,
                "probability": 1.0,
            },
            {
                "segment": "us_eu_remote",
                "skill_a": "RAG",
                "skill_b": "Python",
                "co_occur_count": 2,
                "probability": 1.0,
            },
        ],
        salary_correlations
        or [
            {
                "segment": "us_eu_remote",
                "skill_or_tech": "PyTorch",
                "avg_min_salary": 160000.0,
                "avg_max_salary": 210000.0,
                "currency": "USD",
                "period": "year",
                "disclosed_count": 2,
            },
            {
                "segment": "india_ai_product",
                "skill_or_tech": "FastAPI",
                "avg_min_salary": 1000000.0,
                "avg_max_salary": 1500000.0,
                "currency": "INR",
                "period": "year",
                "disclosed_count": 1,
            },
        ],
        experience_distribution
        or [
            {
                "segment": "india_ai_product",
                "job_count": 1,
                "no_minimum_count": 1,
                "three_plus_count": 0,
                "five_plus_count": 0,
                "senior_only_count": 0,
            },
            {
                "segment": "us_eu_remote",
                "job_count": 2,
                "no_minimum_count": 0,
                "three_plus_count": 1,
                "five_plus_count": 1,
                "senior_only_count": 0,
            },
        ],
        [{"skills": profile_skills if profile_skills is not None else ["Python", "React"]}],
        [prior_report] if prior_report is not None else [],
    ]


@pytest.mark.asyncio
async def test_analytics_locked_state(app, client):
    app.state.pool = MockPool(
        [
            [{"count": 0}],
            [{"overall_f1": 0.9}],
            [{"status": "success"}],
        ]
    )

    response = await client.get("/api/v1/jobs/analytics")

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] is True
    assert payload["code"] == "METRICS_LOCKED"
    assert "Ingestion corpus or accuracy below minimum quality thresholds" in payload["detail"]


@pytest.mark.asyncio
async def test_analytics_warning_state_defaults_delta_to_zero_without_prior_week(app, client):
    app.state.pool = MockPool(
        analytics_query_results(
            corpus_size=50,
            extracted_count=1,
            segment_counts=[{"segment": "india_ai_product", "job_count": 1}],
            top_skills=[
                {
                    "segment": "india_ai_product",
                    "skill_key": "python",
                    "skill": "Python",
                    "skill_count": 1,
                    "frequency": 1.0,
                }
            ],
            co_occurrences=[],
            salary_correlations=[],
            experience_distribution=[
                {
                    "segment": "india_ai_product",
                    "job_count": 1,
                    "no_minimum_count": 1,
                    "three_plus_count": 0,
                    "five_plus_count": 0,
                    "senior_only_count": 0,
                }
            ],
            profile_skills=["Python"],
            prior_report=None,
        )
    )

    response = await client.get("/api/v1/jobs/analytics")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["system_state"] == "warning"
    assert data["corpus_size"] == 50
    assert data["extracted_coverage"] == 0.02
    assert data["geo_segments"]["india_ai_product"]["job_count"] == 1
    assert data["geo_segments"]["india_ai_product"]["profile_fit_score"] == 1 / 30.0
    assert data["geo_segments"]["india_ai_product"]["profile_fit_delta"] == 0.0


@pytest.mark.asyncio
async def test_analytics_nominal_state(app, client):
    prior_report = {
        "geo_us_eu": {
            "top_skills": [
                {"skill": "Python", "count": 10, "frequency": 1.0},
                {"skill": 123, "count": 1, "frequency": 0.1},
            ]
        },
        "geo_india": {"top_skills": []},
    }
    app.state.pool = MockPool(analytics_query_results(prior_report=prior_report))

    response = await client.get("/api/v1/jobs/analytics")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["system_state"] == "nominal"
    assert data["corpus_size"] == 150
    assert data["extracted_coverage"] == 4 / 150.0

    geo = data["geo_segments"]
    assert geo["unclassified"]["job_count"] == 1

    india_data = geo["india_ai_product"]
    assert india_data["job_count"] == 1
    assert len(india_data["top_skills"]) == 2
    assert india_data["top_skills"][0]["skill"] == "Python"
    assert india_data["top_skills"][0]["count"] == 1
    assert india_data["top_skills"][0]["frequency"] == 1.0
    assert india_data["experience_distribution"] == {
        "no_minimum": 1.0,
        "three_plus": 0.0,
        "five_plus": 0.0,
        "senior_only": 0.0,
    }

    remote_data = geo["us_eu_remote"]
    assert remote_data["job_count"] == 2
    assert {skill["skill"] for skill in remote_data["top_skills"]} == {
        "Python",
        "pgvector",
        "RAG",
    }
    assert len(remote_data["co_occurrences"]) == 6
    assert remote_data["co_occurrences"][0]["co_occur_count"] == 2
    assert remote_data["co_occurrences"][0]["probability"] == 1.0
    assert remote_data["experience_distribution"] == {
        "no_minimum": 0.0,
        "three_plus": 0.5,
        "five_plus": 0.5,
        "senior_only": 0.0,
    }
    assert abs(remote_data["profile_fit_score"] - (1 / 30.0)) < 1e-6
    assert abs(remote_data["profile_fit_delta"] - 0.0) < 1e-6
    assert {gap["skill"] for gap in remote_data["skill_gap"]} == {"pgvector", "RAG"}
    assert remote_data["skill_gap"][0]["in_profile"] is False


@pytest.mark.asyncio
async def test_analytics_returns_standard_error_envelope_on_query_failure(app, client):
    app.state.pool = MockPool([], execute_error=RuntimeError("database exploded"))

    response = await client.get("/api/v1/jobs/analytics")

    assert response.status_code == 500
    assert response.json() == {
        "error": True,
        "code": "DB_CONNECTION_ERROR",
        "detail": "Database query execution failure.",
    }


@pytest.mark.asyncio
async def test_analytics_returns_standard_error_envelope_when_pool_missing(app, client):
    app.state.pool = None

    response = await client.get("/api/v1/jobs/analytics")

    assert response.status_code == 500
    assert response.json() == {
        "error": True,
        "code": "DB_CONNECTION_ERROR",
        "detail": "Database query execution failure.",
    }
