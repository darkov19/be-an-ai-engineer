import json
import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from backend.services.company_discovery import (
    BOUNDED_COMPANY_PATHS,
    CompanySignal,
    CompanySignalResolution,
    normalize_company_domain,
)
from backend.services.source_discovery import (
    MAX_PAGE_BYTES,
    detect_candidates_in_text,
    normalize_ats_url,
    validate_candidate_source,
)

ORDERED_BOUNDED_COMPANY_PATHS = ("/careers", "/jobs", "/join-us", "/work-with-us", "/company/careers")
MAX_SITEMAP_URLS = 10


class JSONLDParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_json_ld = False
        self._parts: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = {name.lower(): value for name, value in attrs if value}
        if tag.lower() == "script" and attrs_dict.get("type", "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._parts = []

    def handle_data(self, data):
        if self._in_json_ld:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_json_ld:
            self.blocks.append("".join(self._parts))
            self._in_json_ld = False
            self._parts = []


def build_bounded_company_urls(company_domain_or_url: str) -> list[str]:
    raw = company_domain_or_url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []
    base = f"https://{parsed.netloc.lower()}"
    return [f"{base}{path}" for path in ORDERED_BOUNDED_COMPANY_PATHS]


def _same_company_host(candidate_host: str, company_host: str) -> bool:
    left = candidate_host.lower().removeprefix("www.")
    right = company_host.lower().removeprefix("www.")
    return left == right


def parse_sitemap_locations(xml_text: str, company_host: str, limit: int = MAX_SITEMAP_URLS) -> list[str]:
    urls = []
    seen = set()
    for raw_url in re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml_text or "", flags=re.IGNORECASE):
        parsed = urlparse(raw_url.strip())
        if parsed.scheme not in {"http", "https"} or not _same_company_host(parsed.netloc, company_host):
            continue
        normalized = raw_url.strip()
        if normalized not in seen:
            urls.append(normalized)
            seen.add(normalized)
        if len(urls) >= limit:
            break
    return urls


def extract_sitemap_urls_from_robots(robots_text: str, company_host: str, limit: int = MAX_SITEMAP_URLS) -> list[str]:
    urls = []
    for line in (robots_text or "").splitlines():
        if not line.lower().startswith("sitemap:"):
            continue
        raw_url = line.split(":", 1)[1].strip()
        parsed = urlparse(raw_url)
        if parsed.scheme in {"http", "https"} and _same_company_host(parsed.netloc, company_host):
            urls.append(raw_url)
        if len(urls) >= limit:
            break
    return urls


def extract_jobposting_json_ld(html: str) -> list[dict]:
    parser = JSONLDParser()
    try:
        parser.feed(html or "")
    except Exception:
        return []

    postings = []
    for block in parser.blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        postings.extend(_find_jobpostings(parsed))
    return postings


def _find_jobpostings(value) -> list[dict]:
    if isinstance(value, list):
        postings = []
        for item in value:
            postings.extend(_find_jobpostings(item))
        return postings
    if not isinstance(value, dict):
        return []
    item_type = value.get("@type")
    types = item_type if isinstance(item_type, list) else [item_type]
    found = [value] if "JobPosting" in types else []
    if "@graph" in value:
        found.extend(_find_jobpostings(value["@graph"]))
    return found


async def _fetch_text(client: httpx.AsyncClient, url: str, max_bytes: int = MAX_PAGE_BYTES) -> str:
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("page exceeds maximum response size")

        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ValueError("page exceeds maximum response size")
    encoding = response.encoding or "utf-8"
    return bytes(body).decode(encoding, errors="replace")


async def _candidate_urls_for_signal(client: httpx.AsyncClient, signal: CompanySignal) -> list[str]:
    urls = []
    if signal.careers_url:
        parsed_careers = urlparse(signal.careers_url)
        if (parsed_careers.path.rstrip("/") or "/") in BOUNDED_COMPANY_PATHS:
            urls.append(signal.careers_url)
    normalized_domain = signal.normalized_domain or normalize_company_domain(signal.company_domain)
    if normalized_domain:
        urls.extend(build_bounded_company_urls(normalized_domain))
        host = urlparse(f"https://{normalized_domain}").netloc
        try:
            robots_text = await _fetch_text(client, f"https://{host}/robots.txt")
            urls.extend(extract_sitemap_urls_from_robots(robots_text, host))
        except Exception:
            pass
        try:
            sitemap_text = await _fetch_text(client, f"https://{host}/sitemap.xml")
            urls.extend(parse_sitemap_locations(sitemap_text, host))
        except Exception:
            pass

    deduped = []
    seen = set()
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


async def resolve_company_signal(signal: CompanySignal) -> CompanySignalResolution:
    if signal.direct_ats_url:
        direct = normalize_ats_url(signal.direct_ats_url, "company_signal", signal.company_name)
        if not direct:
            return CompanySignalResolution(signal, "rejected", rejection_reason="unsupported_ats")
        validation = await validate_candidate_source(direct)
        if validation.validation_status == "validated":
            return CompanySignalResolution(signal, "resolved", direct, validation)
        return CompanySignalResolution(
            signal,
            "rejected" if validation.validation_status == "rejected" else "error",
            direct,
            validation,
            rejection_reason=validation.rejection_reason or "validation_rejected",
            last_error=validation.last_error,
        )

    json_ld_evidence = []
    last_fetch_error: Optional[str] = None
    rejected_result = None
    error_result = None
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for page_url in await _candidate_urls_for_signal(client, signal):
            try:
                html = await _fetch_text(client, page_url)
            except Exception as exc:
                last_fetch_error = str(exc)
                continue

            json_ld_evidence.extend(extract_jobposting_json_ld(html))
            candidates, _ = detect_candidates_in_text(html, "company_signal", signal.company_name, base_url=page_url)
            for candidate in candidates:
                validation = await validate_candidate_source(candidate)
                if validation.validation_status == "validated":
                    candidate.metadata.setdefault("source_urls", [candidate.source_url])
                    candidate.metadata["company_signal_evidence_url"] = signal.evidence_url
                    return CompanySignalResolution(signal, "resolved", candidate, validation, json_ld_evidence)
                if validation.validation_status == "error" and error_result is None:
                    error_result = validation
                if validation.validation_status == "rejected" and rejected_result is None:
                    rejected_result = validation

            # Inspect script/config text and anchors from known ATS URLs without following links.
            candidates, _ = detect_candidates_in_text(html, "company_signal", signal.company_name, base_url=urljoin(page_url, "/"))
            if candidates:
                continue

    if rejected_result:
        return CompanySignalResolution(
            signal,
            "rejected",
            rejected_result.candidate,
            rejected_result,
            json_ld_evidence,
            rejection_reason=rejected_result.rejection_reason or "validation_rejected",
            last_error=rejected_result.last_error,
        )
    if error_result:
        return CompanySignalResolution(
            signal,
            "error",
            error_result.candidate,
            error_result,
            json_ld_evidence,
            rejection_reason="validation_error",
            last_error=error_result.last_error,
        )
    if json_ld_evidence:
        return CompanySignalResolution(
            signal,
            "unresolved",
            json_ld_evidence=json_ld_evidence,
            rejection_reason="json_ld_unvalidated",
        )
    if last_fetch_error:
        return CompanySignalResolution(
            signal,
            "error",
            rejection_reason="validation_error",
            last_error=last_fetch_error,
        )
    return CompanySignalResolution(signal, "unresolved", rejection_reason="no_canonical_source_found")
