import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.evaluator import (
    calculate_list_metrics,
    compare_categorical,
    compare_salary_band,
    run_evaluation,
)
from backend.llm.hermes import HermesProxyConnectionError
from backend.llm.schemas import SalaryBand

def test_calculate_list_metrics():
    # Both empty -> 1.0
    assert calculate_list_metrics([], []) == (1.0, 1.0, 1.0)
    # One empty -> 0.0
    assert calculate_list_metrics(["Python"], []) == (0.0, 0.0, 0.0)
    assert calculate_list_metrics([], ["Python"]) == (0.0, 0.0, 0.0)
    # Identical -> 1.0
    assert calculate_list_metrics(["Python", "FastAPI"], ["FastAPI", "Python"]) == (1.0, 1.0, 1.0)
    # Partial overlap
    assert calculate_list_metrics(["Python", "FastAPI"], ["FastAPI", "React"]) == (0.5, 0.5, 0.5)
    # Case insensitivity & whitespace stripping
    assert calculate_list_metrics(["Python"], ["  python "]) == (1.0, 1.0, 1.0)

def test_compare_categorical():
    assert compare_categorical("entry", "entry") == 1.0
    assert compare_categorical("entry", "ENTRY") == 1.0
    assert compare_categorical("entry", " mid ") == 0.0
    assert compare_categorical("", "") == 1.0

def test_compare_salary_band():
    not_disclosed = SalaryBand(kind="not_disclosed")
    disclosed_usd = SalaryBand(kind="disclosed", currency="USD", min_amount=100000, max_amount=150000, period="year")
    disclosed_inr = SalaryBand(kind="disclosed", currency="INR", min_amount=100000, max_amount=150000, period="year")
    disclosed_usd_monthly = SalaryBand(kind="disclosed", currency="USD", min_amount=100000, max_amount=150000, period="month")
    disclosed_usd_diff_min = SalaryBand(kind="disclosed", currency="USD", min_amount=90000, max_amount=150000, period="year")

    assert compare_salary_band(not_disclosed, not_disclosed) == 1.0
    assert compare_salary_band(not_disclosed, disclosed_usd) == 0.0
    assert compare_salary_band(disclosed_usd, disclosed_usd) == 1.0
    assert compare_salary_band(disclosed_usd, disclosed_inr) == 0.0
    assert compare_salary_band(disclosed_usd, disclosed_usd_monthly) == 0.0
    assert compare_salary_band(disclosed_usd, disclosed_usd_diff_min) == 0.0

@pytest.mark.asyncio
async def test_run_evaluation_dry_run_success(tmp_path):
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [
        {
            "eval_id": "eval-011",
            "split": "held_out",
            "job_url": "http://test",
            "source_slug": "test",
            "title": "Junior AI Engineer",
            "company": "TestCo",
            "raw_text_excerpt": "excerpt",
            "expected_skills": ["Python"],
            "expected_seniority": "entry",
            "expected_tech_stack": ["Python"],
            "expected_salary_band": {"kind": "not_disclosed"},
            "expected_remote_policy": "onsite",
            "expected_role_archetype": "llm_app_engineer",
            "annotation_notes": "notes",
        }
    ]
    mock_cursor.fetchone.side_effect = [
        None,  # SELECT last_run (no runs yet)
        (42,)  # INSERT returning id
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor

    res = await run_evaluation(mock_conn, split="held_out", dry_run=True, summary_dir=tmp_path)
    assert res["run_id"] == 42
    assert res["overall_metrics"]["f1"] == 1.0
    assert res["accuracy_regression"] is False
    assert res["summary_path"].startswith(str(tmp_path))
    assert any(tmp_path.glob("run-summary-*.json"))

@pytest.mark.asyncio
async def test_run_evaluation_regression_detection(tmp_path):
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [
        {
            "eval_id": "eval-011",
            "split": "held_out",
            "job_url": "http://test",
            "source_slug": "test",
            "title": "Junior AI Engineer",
            "company": "TestCo",
            "raw_text_excerpt": "excerpt",
            "expected_skills": ["Python"],
            "expected_seniority": "entry",
            "expected_tech_stack": ["Python"],
            "expected_salary_band": {"kind": "not_disclosed"},
            "expected_remote_policy": "onsite",
            "expected_role_archetype": "llm_app_engineer",
            "annotation_notes": "notes",
        }
    ]

    mock_cursor.fetchone.side_effect = [
        {"overall_f1": 1.0},  # Last run F1
        (43,)  # DB inserted ID
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor

    res = await run_evaluation(
        mock_conn,
        split="held_out",
        dry_run=True,
        perturb_dry_run=True,
        summary_dir=tmp_path,
    )
    assert res["run_id"] == 43
    assert res["accuracy_regression"] is True

@pytest.mark.asyncio
async def test_run_evaluation_hermes_offline():
    mock_conn = MagicMock()
    with patch("backend.services.evaluator.check_hermes_proxy_health", side_effect=HermesProxyConnectionError("Offline")):
        with pytest.raises(HermesProxyConnectionError):
            await run_evaluation(mock_conn, split="held_out", dry_run=False)
    mock_conn.cursor.assert_not_called()

@pytest.mark.asyncio
async def test_run_evaluation_non_dry_run_uses_hermes_payload_and_persists(tmp_path):
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [
        {
            "eval_id": "eval-011",
            "split": "held_out",
            "job_url": "http://test",
            "source_slug": "test",
            "title": "Junior AI Engineer",
            "company": "TestCo",
            "raw_text_excerpt": "Technical skills: Python. Onsite.",
            "expected_skills": ["Python"],
            "expected_seniority": "entry",
            "expected_tech_stack": ["Python"],
            "expected_salary_band": {"kind": "not_disclosed"},
            "expected_remote_policy": "onsite",
            "expected_role_archetype": "llm_app_engineer",
            "annotation_notes": "notes",
        }
    ]
    mock_cursor.fetchone.side_effect = [
        None,
        (44,),
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
    hermes_payload = {
        "items": [
            {
                "job_id": 1,
                "skills": ["Python"],
                "seniority": "entry",
                "tech_stack": ["Python"],
                "salary_band": {"kind": "not_disclosed"},
                "remote_policy": "onsite",
                "role_archetype": "llm_app_engineer",
            }
        ]
    }

    with patch("backend.services.evaluator.check_hermes_proxy_health", new=AsyncMock()) as mock_health:
        with patch("backend.services.evaluator._post_to_hermes", new=AsyncMock(return_value=hermes_payload)) as mock_post:
            res = await run_evaluation(
                mock_conn,
                split="held_out",
                prompt_version="extraction_v1",
                dry_run=False,
                summary_dir=tmp_path,
            )

    mock_health.assert_awaited_once()
    mock_post.assert_awaited_once()
    assert mock_post.await_args.kwargs["prompt_version"] == "extraction_v1"
    assert res["run_id"] == 44
    assert res["overall_metrics"]["f1"] == 1.0
    assert res["summary_path"].startswith(str(tmp_path))
