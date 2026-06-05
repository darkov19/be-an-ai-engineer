import struct
from datetime import date
from pathlib import Path

import pytest

from backend.services import report_publisher


def sample_snapshot() -> dict:
    return {
        "run_date": date(2026, 6, 6),
        "report_slug": "2026-W23",
        "corpus_size": 142,
        "per_source_counts": {"yc_waas": 40, "hn": 25},
        "eval_accuracy": 0.82,
        "geo_us_eu": {
            "top_skills": [
                {"skill": "FastAPI <script>", "frequency": 12},
                {"skill": "RAG", "frequency": 9},
            ],
            "experience_distribution": {"no_minimum": 0.2, "three_plus": 0.4, "five_plus": 0.3, "senior_only": 0.1},
            "profile_fit_score": 0.5,
            "profile_fit_delta": 0.08,
        },
        "geo_india": {
            "top_skills": [
                {"skill": "LLM", "frequency": 11},
                {"skill": "Agents", "frequency": 7},
            ],
            "experience_distribution": {"no_minimum": 0.1, "three_plus": 0.5, "five_plus": 0.3, "senior_only": 0.1},
            "profile_fit_score": 0.4,
            "profile_fit_delta": -0.02,
        },
        "coverage_diagnostics": {"notes": ["LLM-derived <coverage> note"]},
        "accountability_summary": {"summary": "Loop B evidence pending"},
        "profile_freshness": {"is_stale": True, "message": "Profile is stale"},
        "commit_sha": "abc123",
        "deployment_url": "https://example.vercel.app/reports/2026-W23/",
    }


def test_build_report_slug_uses_iso_week():
    assert report_publisher.build_report_slug(date(2026, 6, 6)) == "2026-W23"


def test_render_weekly_report_html_escapes_generated_content_and_includes_required_blocks():
    html = report_publisher.render_weekly_report_html(sample_snapshot())

    assert "FastAPI &lt;script&gt;" in html
    assert "<script>alert" not in html
    assert "og:image" in html
    assert "Minimum Experience Thresholds" in html
    assert "Profile Fit Delta" in html
    assert "Accountability / Loop B" in html
    assert "Profile Freshness" in html
    assert "window.history.replaceState" in html


def test_render_archive_html_sorts_newest_first_and_empty_state():
    rows = [
        {"run_date": date(2026, 5, 30), "report_slug": "2026-W22", "corpus_size": 80, "eval_accuracy": 0.7},
        {"run_date": date(2026, 6, 6), "report_slug": "2026-W23", "corpus_size": 142, "eval_accuracy": 0.82},
    ]

    html = report_publisher.render_archive_html(rows)
    assert html.index("2026-W23") < html.index("2026-W22")
    assert "No weekly reports have been published yet." in report_publisher.render_archive_html([])


def test_render_archive_html_normalizes_persisted_report_paths():
    html = report_publisher.render_archive_html([
        {"run_date": date(2026, 6, 6), "report_slug": "2026-W23", "report_path": "reports/2026-W23/index.html"}
    ])

    assert 'href="/reports/2026-W23/index.html"' in html


def test_write_report_assets_creates_static_report_archive_and_og(tmp_path: Path):
    paths = report_publisher.write_report_assets(sample_snapshot(), tmp_path)

    report_path = tmp_path / "reports" / "2026-W23" / "index.html"
    archive_path = tmp_path / "archive" / "index.html"
    og_path = tmp_path / "reports" / "2026-W23" / "og.png"
    assert paths["report_html"] == report_path
    assert report_path.exists()
    assert archive_path.exists()
    assert og_path.exists()
    assert og_path.stat().st_size > 1000
    assert og_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", og_path.read_bytes()[16:24]) == (1200, 630)


def test_generate_og_image_is_deterministic_for_fixed_input():
    first = report_publisher.generate_og_image_png(sample_snapshot())
    second = report_publisher.generate_og_image_png(sample_snapshot())
    assert first == second


def test_v010_migration_keeps_run_date_index_and_adds_publish_columns():
    migration = (Path(__file__).resolve().parents[2] / "db/migrations/V010__add_weekly_report_publish_metadata.sql").read_text(encoding="utf-8")
    assert "report_slug" in migration
    assert "snapshot JSONB" in migration
    assert "idx_weekly_reports_run_date" in migration
