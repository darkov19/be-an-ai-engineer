import pytest
from pydantic import ValidationError

from backend.llm.schemas import (
    EXTRACTION_SCHEMA_VERSION,
    ExtractionBatch,
    ExtractedJobSignal,
    SalaryBand,
)


def test_extraction_batch_accepts_valid_not_disclosed_salary():
    batch = ExtractionBatch.model_validate(
        {
            "items": [
                {
                    "job_id": 42,
                    "skills": ["Python", "FastAPI", "RAG"],
                    "seniority": "senior",
                    "tech_stack": ["Postgres", "httpx"],
                    "salary_band": {"kind": "not_disclosed"},
                    "remote_policy": "hybrid",
                    "role_archetype": "llm_app_engineer",
                }
            ]
        }
    )

    item = batch.items[0]
    assert item.job_id == 42
    assert item.salary_band.kind == "not_disclosed"
    assert EXTRACTION_SCHEMA_VERSION == "v1"


def test_salary_band_accepts_disclosed_range_without_fabrication():
    salary = SalaryBand.model_validate(
        {
            "kind": "disclosed",
            "currency": "USD",
            "min_amount": 150000,
            "max_amount": 210000,
            "period": "year",
        }
    )

    assert salary.currency == "USD"
    assert salary.min_amount == 150000
    assert salary.max_amount == 210000


def test_schema_rejects_unknown_enum_values_and_extra_fields():
    with pytest.raises(ValidationError):
        ExtractedJobSignal.model_validate(
            {
                "job_id": 7,
                "skills": ["Python"],
                "seniority": "principal",
                "tech_stack": [],
                "salary_band": {"kind": "not_disclosed"},
                "remote_policy": "remote",
                "role_archetype": "unknown",
                "commentary": "extra text",
            }
        )


def test_disclosed_salary_requires_currency_and_amount():
    with pytest.raises(ValidationError):
        SalaryBand.model_validate({"kind": "disclosed", "currency": "USD"})


def test_not_disclosed_salary_rejects_fabricated_range():
    with pytest.raises(ValidationError):
        SalaryBand.model_validate(
            {
                "kind": "not_disclosed",
                "currency": "USD",
                "min_amount": 100000,
            }
        )
