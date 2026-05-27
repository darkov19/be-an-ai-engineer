import pytest

from backend.scripts.corpus_sanity import collect_corpus_sanity


class MockCursor:
    def __init__(self, results):
        self.results = results
        self.index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, vars=None):
        pass

    async def fetchone(self):
        result = self.results[self.index]
        self.index += 1
        return result

    async def fetchall(self):
        result = self.results[self.index]
        self.index += 1
        return result


class MockConnection:
    def __init__(self, results):
        self.cursor_obj = MockCursor(results)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self, *args, **kwargs):
        return self.cursor_obj


class MockPool:
    def __init__(self, results):
        self.results = results

    def connection(self):
        return MockConnection(self.results)


@pytest.mark.asyncio
async def test_collect_corpus_sanity_report():
    pool = MockPool(
        [
            {"total_jobs": 3},
            [{"source_slug": "yc_waas", "count": 3}],
            [{"status": "backlog", "count": 3}],
            {"empty_raw_text_jobs": 0},
            {"duplicate_url_rows": 0},
            {
                "id": 7,
                "status": "success",
                "source_counts": {"yc_waas": 3},
                "error_message": None,
                "execution_time_seconds": 1.2,
                "run_timestamp": "2026-05-27T00:00:00+05:30",
            },
            {"total_runs": 2, "failed_runs": 1, "runs_with_errors": 1},
        ]
    )

    report = await collect_corpus_sanity(pool)

    assert report["total_jobs"] == 3
    assert report["per_source_counts"] == {"yc_waas": 3}
    assert report["status_counts"] == {"backlog": 3}
    assert report["empty_raw_text_jobs"] == 0
    assert report["duplicate_url_rows"] == 0
    assert report["latest_attempted_source_counts"] == {"yc_waas": 3}
    assert report["run_failure_rate"] == 0.5
    assert report["run_error_rate"] == 0.5
