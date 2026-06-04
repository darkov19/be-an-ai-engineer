# Runtime Artifact Policy

This project produces runtime JSON artifacts as part of ingestion, extraction, evaluation, and quality-gate runs. These files are useful evidence, but unreviewed local output should not enter source control accidentally.

## Default Handling

Root-level runtime artifacts are ignored by default:

- `kill-criterion-fired-*.json`
- `run-summary-*.json`
- `extraction-run-*.json`

These files represent local execution state unless they are deliberately promoted as project evidence.

## Curated Evidence

Commit runtime artifacts only when they are intentionally part of the project record:

- Evaluation summaries that document extraction quality for a public write-up.
- Kill-criterion artifacts that document a real locked run and recovery path.
- Corpus or discovery reports that explain a planning or implementation decision.

Curated artifacts should live under `_bmad-output/implementation-artifacts/` and be referenced by the relevant story, retrospective, README section, or methodology document. If a file is ignored but should be committed as curated evidence, force-add it deliberately after reviewing that it contains no secrets, raw prompt bodies, full proxy responses, credentials, or large raw job text.

## Review Checklist

- The artifact supports a specific project decision or public evidence claim.
- The artifact is not a transient local test output.
- Secrets, API keys, credentials, raw LLM responses, and large raw job text are absent.
- The filename includes the run date or week identifier.
- A nearby markdown document explains why the artifact matters.
