# Source Discovery Provider Review Checklist

Use this checklist for every source-discovery provider change before moving a story to `done`.

## Required Checks

- **Disabled state:** Provider returns explicit disabled or missing-configuration diagnostics and does not disappear from `company_signals.provider_diagnostics`.
- **Official surface:** Provider uses only the approved API or public surface named in the story; no rendered-page scraping, browser automation, login/session state, or unofficial marketplace ingestion is added.
- **Trust boundary:** Provider output remains evidence until it passes `normalize_company_signal`, bounded canonical resolution, and parser-backed ATS validation. Provider code must not directly activate `job_sources`.
- **Caps:** Query/page/post/record caps are enforced before extra work is scheduled. Orchestration-wide `DISCOVERY_MAX_COMPANY_SIGNALS_PER_RUN` and `DISCOVERY_MAX_COMPANY_RESOLUTIONS_PER_RUN` still bound the full run.
- **Quota state:** Durable quota or rate state cannot be bypassed by repeated local runs where the provider has a quota budget.
- **Malformed payloads:** Bad JSON, unexpected shapes, missing fields, and malformed rows become rejected diagnostics or provider errors, not unhandled exceptions.
- **Response limits:** HTTP response-size caps are enforced before processing large bodies where the provider fetches remote content.
- **Redirects:** Redirect targets are validated when redirects are followed; disallowed final URLs are rejected.
- **Secret redaction:** API keys, tokens, client secrets, and credential-like query parameters are not written to logs, reports, diagnostics, exceptions, metadata, or test snapshots.
- **Failure isolation:** One failed provider or failed company signal does not abort the whole discovery run unless every configured provider fails.
- **Persistence exposure:** Provider diagnostics, provider errors, unsupported URL counts, and provider yield remain visible in the discovery report and `/api/v1/ingest/company-signals`.
- **Yield attribution:** Validated sources, newly activated sources, revalidations, unsupported URLs, and repeated rejections are attributed without double-counting.
- **Regression coverage:** Tests cover disabled/enabled paths, cap exhaustion, malformed payloads, transport/API errors, redaction, report compatibility, and API diagnostics.

## Review Outcome

The review is incomplete if any required check is untested, unobservable in diagnostics, or only guaranteed by provider-specific assumptions.
