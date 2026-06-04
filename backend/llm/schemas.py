from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EXTRACTION_SCHEMA_VERSION = "v1"

Seniority = Literal["entry", "mid", "senior", "staff_plus", "unknown"]
RemotePolicy = Literal["remote", "hybrid", "onsite", "flexible", "unknown"]
RoleArchetype = Literal[
    "llm_app_engineer",
    "ai_product_engineer",
    "agent_engineer",
    "ml_platform_engineer",
    "data_ai_engineer",
    "research_engineer",
    "unknown",
]
SalaryKind = Literal["not_disclosed", "disclosed"]
SalaryPeriod = Literal["hour", "day", "month", "year", "unknown"]


class SalaryBand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: SalaryKind
    currency: str | None = None
    min_amount: int | None = Field(default=None, ge=0)
    max_amount: int | None = Field(default=None, ge=0)
    period: SalaryPeriod | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter ISO code")
        return normalized

    @model_validator(mode="after")
    def validate_salary_shape(self) -> "SalaryBand":
        if self.kind == "not_disclosed":
            if any(
                value is not None
                for value in (self.currency, self.min_amount, self.max_amount, self.period)
            ):
                raise ValueError("not_disclosed salary cannot include range fields")
            return self

        if self.currency is None:
            raise ValueError("disclosed salary requires currency")
        if self.min_amount is None and self.max_amount is None:
            raise ValueError("disclosed salary requires at least one amount")
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("min_amount cannot exceed max_amount")
        return self


class ExtractedJobSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    job_id: int = Field(gt=0)
    skills: list[str] = Field(default_factory=list, max_length=30)
    seniority: Seniority
    tech_stack: list[str] = Field(default_factory=list, max_length=30)
    salary_band: SalaryBand
    remote_policy: RemotePolicy
    role_archetype: RoleArchetype

    @field_validator("skills", "tech_stack")
    @classmethod
    def clean_string_list(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("list values must be non-empty strings")
            key = item.casefold()
            if key not in seen:
                cleaned.append(item)
                seen.add(key)
        return cleaned


class ExtractionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ExtractedJobSignal] = Field(default_factory=list)
