import json
from collections import Counter
from dataclasses import dataclass, field
from numbers import Number
from typing import Optional
from urllib.parse import urlparse, urlunparse

BOUNDED_COMPANY_PATHS = {"/careers", "/jobs", "/join-us", "/work-with-us", "/company/careers"}


@dataclass
class CompanySignal:
    provider: str
    evidence_url: str
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    normalized_domain: Optional[str] = None
    careers_url: Optional[str] = None
    direct_ats_url: Optional[str] = None
    confidence: Optional[float] = None
    category_hints: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class CompanySignalNormalization:
    signal: Optional[CompanySignal]
    rejection_reason: Optional[str] = None


@dataclass
class CompanySignalResolution:
    signal: CompanySignal
    status: str
    resolved_candidate: Optional[object] = None
    validation_result: Optional[object] = None
    json_ld_evidence: list[dict] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class CompanyDiscoveryRunResult:
    signals: list[CompanySignal] = field(default_factory=list)
    resolutions: list[CompanySignalResolution] = field(default_factory=list)
    provider_errors: dict[str, str] = field(default_factory=dict)
    provider_diagnostics: dict[str, dict] = field(default_factory=dict)
    provider_yield: dict = field(default_factory=dict)


def _normalized_http_url(raw_url: str) -> Optional[str]:
    raw_url = (raw_url or "").strip()
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunparse(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", parsed.query, ""))


def _json_safe_dict(value) -> dict:
    if not isinstance(value, dict):
        return {}
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, default=str))
    return value


def _dedupe_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    deduped = []
    seen = set()
    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            deduped.append(text)
            seen.add(text)
    return deduped


def _normalized_path(raw_url: str) -> str:
    return urlparse(raw_url).path.rstrip("/") or "/"


def normalize_company_domain(raw_domain: Optional[str]) -> Optional[str]:
    if not raw_domain:
        return None
    candidate = raw_domain.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if "." not in host:
        return None
    return host


def normalize_company_signal(signal: CompanySignal) -> CompanySignalNormalization:
    provider = str(getattr(signal, "provider", "") or "").strip()
    if not provider:
        return CompanySignalNormalization(None, "missing_provider")

    evidence_url = _normalized_http_url(getattr(signal, "evidence_url", ""))
    if not evidence_url:
        return CompanySignalNormalization(None, "invalid_evidence_url")

    raw_careers_url = getattr(signal, "careers_url", None)
    careers_url = _normalized_http_url(raw_careers_url) if raw_careers_url else None
    if raw_careers_url and not careers_url:
        return CompanySignalNormalization(None, "invalid_careers_url")
    if careers_url and _normalized_path(careers_url) not in BOUNDED_COMPANY_PATHS:
        return CompanySignalNormalization(None, "invalid_careers_url")

    raw_direct_ats_url = getattr(signal, "direct_ats_url", None)
    direct_ats_url = _normalized_http_url(raw_direct_ats_url) if raw_direct_ats_url else None
    if raw_direct_ats_url and not direct_ats_url:
        return CompanySignalNormalization(None, "invalid_direct_ats_url")

    raw_company_domain = getattr(signal, "company_domain", None)
    normalized_domain = normalize_company_domain(raw_company_domain)
    if raw_company_domain and not normalized_domain:
        return CompanySignalNormalization(None, "invalid_domain")

    if not normalized_domain and careers_url:
        normalized_domain = normalize_company_domain(careers_url)
    elif normalized_domain and careers_url and normalize_company_domain(careers_url) != normalized_domain:
        return CompanySignalNormalization(None, "invalid_careers_domain")

    if not normalized_domain and not careers_url and not direct_ats_url:
        return CompanySignalNormalization(None, "missing_company_locator")

    confidence = getattr(signal, "confidence", None)
    if confidence is not None:
        if not isinstance(confidence, Number) or confidence < 0 or confidence > 999.99:
            return CompanySignalNormalization(None, "invalid_confidence")
        confidence = float(confidence)

    return CompanySignalNormalization(
        CompanySignal(
            provider=provider,
            evidence_url=evidence_url,
            company_name=str(getattr(signal, "company_name", "") or "").strip() or None,
            company_domain=str(raw_company_domain or "").strip() or None,
            normalized_domain=normalized_domain,
            careers_url=careers_url,
            direct_ats_url=direct_ats_url,
            confidence=confidence,
            category_hints=_dedupe_string_list(getattr(signal, "category_hints", [])),
            metadata=_json_safe_dict(getattr(signal, "metadata", {})),
        )
    )


def company_signal_metrics(result: CompanyDiscoveryRunResult) -> dict:
    status_counts = Counter(resolution.status for resolution in result.resolutions)
    rejection_reasons = Counter(
        resolution.rejection_reason for resolution in result.resolutions if resolution.rejection_reason
    )
    provider_counts = Counter(signal.provider for signal in result.signals)
    return {
        "signal_count": len(result.signals),
        "resolved_count": status_counts.get("resolved", 0),
        "unresolved_count": status_counts.get("unresolved", 0),
        "rejected_count": status_counts.get("rejected", 0),
        "error_count": status_counts.get("error", 0) + len(result.provider_errors),
        "counts_by_provider": dict(provider_counts),
        "rejection_reasons": dict(rejection_reasons),
        "provider_errors": dict(result.provider_errors),
        "provider_diagnostics": dict(result.provider_diagnostics),
    }


async def persist_company_discovery_results(
    pool,
    result: CompanyDiscoveryRunResult,
    execution_time_seconds: float,
    error_message: Optional[str],
) -> None:
    metrics = company_signal_metrics(result)
    status = "success" if result.signals or result.provider_errors or result.provider_diagnostics else "failure"
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO company_discovery_runs (
                        status, provider_counts, resolved_count, unresolved_count, rejected_count,
                        error_count, rejection_reasons, metadata, error_message, execution_time_seconds
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        status,
                        json.dumps(metrics["counts_by_provider"]),
                        metrics["resolved_count"],
                        metrics["unresolved_count"],
                        metrics["rejected_count"],
                        metrics["error_count"],
                        json.dumps(metrics["rejection_reasons"]),
                        json.dumps(
                            {
                                "provider_errors": result.provider_errors,
                                "provider_diagnostics": result.provider_diagnostics,
                                "provider_yield": result.provider_yield,
                            },
                            default=str,
                        ),
                        error_message,
                        execution_time_seconds,
                    ),
                )
                row = await cur.fetchone()
                run_id = row[0] if row else None

                for resolution in result.resolutions:
                    signal = resolution.signal
                    candidate = resolution.resolved_candidate
                    validation = resolution.validation_result
                    metadata = dict(signal.metadata)
                    if candidate and candidate.metadata:
                        metadata.update(candidate.metadata)
                    await cur.execute(
                        """
                        INSERT INTO company_signals (
                            run_id, provider, company_name, company_domain, normalized_domain,
                            careers_url, direct_ats_url, evidence_url, confidence, category_hints,
                            status, resolved_ats, resolved_slug, resolved_source_url, json_ld_evidence,
                            rejection_reason, last_error, metadata, last_seen_at, resolved_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, CURRENT_TIMESTAMP,
                            CASE WHEN %s = 'resolved' THEN CURRENT_TIMESTAMP ELSE NULL END
                        )
                        ON CONFLICT (provider, evidence_url, normalized_domain, direct_ats_url)
                        DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            company_name = EXCLUDED.company_name,
                            company_domain = EXCLUDED.company_domain,
                            careers_url = EXCLUDED.careers_url,
                            confidence = EXCLUDED.confidence,
                            category_hints = EXCLUDED.category_hints,
                            status = EXCLUDED.status,
                            resolved_ats = EXCLUDED.resolved_ats,
                            resolved_slug = EXCLUDED.resolved_slug,
                            resolved_source_url = EXCLUDED.resolved_source_url,
                            json_ld_evidence = EXCLUDED.json_ld_evidence,
                            rejection_reason = EXCLUDED.rejection_reason,
                            last_error = EXCLUDED.last_error,
                            metadata = EXCLUDED.metadata,
                            last_seen_at = CURRENT_TIMESTAMP,
                            resolved_at = EXCLUDED.resolved_at
                        """,
                        (
                            run_id,
                            signal.provider,
                            signal.company_name,
                            signal.company_domain,
                            signal.normalized_domain,
                            signal.careers_url,
                            signal.direct_ats_url,
                            signal.evidence_url,
                            signal.confidence,
                            json.dumps(signal.category_hints),
                            resolution.status,
                            candidate.ats if candidate else None,
                            candidate.slug if candidate else None,
                            candidate.source_url if candidate else None,
                            json.dumps(resolution.json_ld_evidence),
                            resolution.rejection_reason,
                            resolution.last_error,
                            json.dumps(metadata),
                            resolution.status,
                        ),
                    )

                    if (
                        validation
                        and validation.validation_status == "validated"
                        and candidate
                        and candidate.ats
                        and candidate.slug
                    ):
                        await cur.execute(
                            """
                            INSERT INTO job_sources (
                                company, ats, slug, source_url, discovery_method, validation_status, active,
                                job_count, usable_job_count, last_validated_at, last_success_at, last_error, metadata
                            )
                            VALUES (%s, %s, %s, %s, %s, 'validated', true, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, %s)
                            ON CONFLICT (ats, slug) DO UPDATE SET
                                company = EXCLUDED.company,
                                source_url = EXCLUDED.source_url,
                                discovery_method = EXCLUDED.discovery_method,
                                validation_status = 'validated',
                                active = true,
                                job_count = EXCLUDED.job_count,
                                usable_job_count = EXCLUDED.usable_job_count,
                                last_validated_at = CURRENT_TIMESTAMP,
                                last_success_at = CURRENT_TIMESTAMP,
                                last_error = NULL,
                                metadata = EXCLUDED.metadata,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (
                                candidate.company_hint,
                                candidate.ats,
                                candidate.slug,
                                candidate.source_url,
                                candidate.discovery_method,
                                validation.job_count,
                                validation.usable_job_count,
                                json.dumps(candidate.metadata),
                            ),
                        )
