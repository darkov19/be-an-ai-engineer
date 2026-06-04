import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.llm.client import ExtractionHTTPError
from backend.scripts.run_extraction import _main, run_extraction_for_pool


class EmptyConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *args, **kwargs):
        return self

    async def __aenter_cursor__(self):
        return self

    async def execute(self, query, vars=None):
        pass

    async def fetchall(self):
        return []


class EmptyPool:
    def connection(self):
        return EmptyConnection()


@pytest.mark.asyncio
async def test_run_extraction_for_pool_writes_summary_artifact(monkeypatch, tmp_path):
    async def fake_run_extraction_batch(pool, limit, batch_size, dry_run, summary_dir=None):
        return {
            "run_id": "run-test",
            "selected": 0,
            "extracted": 0,
            "skipped": 0,
            "failed": 0,
            "retryable_errors": 0,
            "dry_run": dry_run,
            "prompt_version": "extraction_v1",
            "schema_version": "v1",
            "elapsed_seconds": 0.01,
            "corpus_selection_note": "jobs.source_slug matched to validated source slugs",
        }

    monkeypatch.setattr("backend.scripts.run_extraction.run_extraction_batch", fake_run_extraction_batch)

    summary = await run_extraction_for_pool(
        EmptyPool(),
        limit=5,
        batch_size=20,
        dry_run=True,
        summary_dir=tmp_path,
    )

    assert summary["dry_run"] is True
    artifact = Path(summary["summary_path"])
    assert artifact.exists()
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["prompt_version"] == "extraction_v1"
    assert data["corpus_selection_note"]


@pytest.mark.asyncio
async def test_main_returns_nonzero_for_extraction_client_failures(monkeypatch, capsys):
    async def fail_run(*args, **kwargs):
        raise ExtractionHTTPError("Hermes extraction request failed for http://127.0.0.1:3000/extract")

    class FakePool:
        def __init__(self, conninfo, open=False):
            pass

        async def open(self):
            pass

        async def close(self):
            pass

    monkeypatch.setattr("backend.scripts.run_extraction.AsyncConnectionPool", FakePool)
    monkeypatch.setattr("backend.scripts.run_extraction.run_extraction_for_pool", fail_run)
    monkeypatch.setattr(sys, "argv", ["run_extraction.py", "--limit", "1"])

    rc = await _main()

    assert rc == 1
    assert "ERROR: Hermes extraction request failed" in capsys.readouterr().out


def test_run_extraction_script_help_works_when_executed_by_path():
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, str(repo_root / "backend" / "scripts" / "run_extraction.py"), "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Run structured job extraction" in result.stdout
