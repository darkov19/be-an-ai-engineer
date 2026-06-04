import pytest
from unittest.mock import patch, AsyncMock
from backend.scripts.run_evaluation import _main

@pytest.mark.asyncio
async def test_cli_runner_dry_run():
    from unittest.mock import MagicMock
    mock_pool = MagicMock()
    mock_pool.open = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
    mock_results = {
        "run_id": 99,
        "run_timestamp": "2026-06-04T12:00:00Z",
        "prompt_version": "extraction_v1",
        "schema_version": "v1",
        "overall_metrics": {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "accuracy_regression": False,
        "field_metrics": {
            "skills": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "tech_stack": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "seniority": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "remote_policy": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "role_archetype": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "salary_band": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
        },
        "detailed_diffs": [
            {
                "eval_id": "eval-011",
                "expected": {"split": "held_out"},
                "actual": {},
                "matching_status": {},
                "mismatched_fields": [],
                "metrics": {},
                "overall_f1": 1.0,
            }
        ]
    }

    with patch("sys.argv", ["run_evaluation.py", "--dry-run"]):
        with patch("backend.scripts.run_evaluation.AsyncConnectionPool", return_value=mock_pool):
            with patch("backend.scripts.run_evaluation.run_evaluation", return_value=mock_results) as mock_run:
                exit_code = await _main()
                assert exit_code == 0
                mock_run.assert_called_once()
