# Evaluation Methodology

The eval harness measures whether structured LLM extraction is reliable enough to drive market analytics. It is intentionally narrow and explicit: the project would rather publish a measured limitation than hide uncertainty behind a polished chart.

## Dataset

The labeled dataset contains 20 job-posting samples seeded into `eval_postings`:

- 10 `train` samples for prompt development and schema sanity checks.
- 10 `held_out` samples for scoring extraction quality.

The held-out split must not be used for prompt examples or prompt tuning. If new examples are needed, add them to the training split or create a new held-out version with the change documented.

## Extracted Fields

Each sample is evaluated across six fields:

- `skills`
- `seniority`
- `tech_stack`
- `salary_band`
- `remote_policy`
- `role_archetype`

The extraction schema lives in `backend/llm/schemas.py`, and the prompt version is recorded with each run so future metric changes can be traced to prompt or schema changes.

## Scoring

List fields (`skills`, `tech_stack`) use set overlap:

- Precision = expected and actual overlap divided by actual values.
- Recall = expected and actual overlap divided by expected values.
- F1 = harmonic mean of precision and recall.
- If both expected and actual lists are empty, precision, recall, and F1 are `1.0`.
- If only one side is empty, precision, recall, and F1 are `0.0`.

Categorical fields (`seniority`, `remote_policy`, `role_archetype`) receive precision, recall, and F1 of `1.0` for an exact normalized match, otherwise `0.0`.

`salary_band` receives `1.0` only when `kind` matches and, for disclosed salary bands, currency, minimum amount, maximum amount, and period all match exactly.

Overall accuracy is the simple average of the six field-level F1 scores.

## Regression Threshold

Each evaluation run compares its overall F1 against the previous run. A regression is flagged when the previous overall F1 minus the current overall F1 is strictly greater than `0.03`.

This threshold catches meaningful extraction drift without treating tiny score movement as a product failure.

## Quality-State Use

The latest held-out F1 feeds the weekly report quality state:

- `locked`: ingestion failed, corpus size is `0`, or both corpus size is below `100` and held-out F1 is below `0.70`.
- `warning`: exactly one of corpus size below `100` or held-out F1 below `0.70` is true after successful ingestion.
- `nominal`: ingestion succeeds and both quality thresholds pass.

Epic 5 analytics must consume this quality state before publishing market metrics.

## Current Limitations

- The dataset is only 20 samples, so it is a baseline quality check rather than a broad benchmark.
- The held-out set may not cover every ATS family, geo segment, role archetype, salary format, or ambiguous seniority wording that appears in the live corpus.
- Exact-match categorical scoring is intentionally strict and can under-credit semantically close outputs.
- Set-overlap scoring for skills and tech stack does not yet account for aliases such as `PostgreSQL` vs. `Postgres`.
- Salary-band scoring treats numeric mismatch as a full miss, even when the extracted range is close.
- The eval harness measures extraction quality, not whether downstream analytics are useful; Epic 5 must still validate ranking and profile-diff behavior against sparse or unknown values.

## Artifact Handling

Evaluation summaries are written as `run-summary-YYYY-WW.json` artifacts. Curated summaries that support public claims should be stored under `_bmad-output/implementation-artifacts/` and reviewed according to `docs/runtime-artifacts.md` before committing.
