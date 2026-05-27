# Initial Labeled Eval Set Rubric

**Purpose:** Provide the ground-truth annotation contract for Epic 3 extraction accuracy.

## Six Extracted Fields

1. **skills**
   - List explicit named skills required or strongly preferred by the posting.
   - Include frameworks, libraries, cloud services, model families, and engineering practices.
   - Do not infer unstated skills from company category alone.

2. **seniority**
   - One of: `entry`, `mid`, `senior`, `staff_plus`, `unknown`.
   - Prefer years-of-experience requirements and title language over compensation or company prestige.

3. **tech_stack**
   - List concrete technologies used to build or operate the product.
   - Keep this narrower than `skills`; exclude generic soft skills and broad duties.

4. **salary_band**
   - One of: `disclosed`, `not_disclosed`.
   - If disclosed, preserve the visible range and currency in notes.

5. **remote_policy**
   - One of: `remote`, `hybrid`, `onsite`, `flexible`, `unknown`.
   - Use location and explicit work-policy text. Do not infer remote from "global" unless stated.

6. **role_archetype**
   - One of: `llm_app_engineer`, `ai_product_engineer`, `agent_engineer`, `ml_platform_engineer`, `data_ai_engineer`, `research_engineer`, `unknown`.
   - Choose the dominant role from responsibilities, not only the title.

## Eval Set Structure

The seed CSV lives at `_bmad-output/planning-artifacts/eval-set-seed.csv`.

Required columns:

- `eval_id`
- `split`
- `job_url`
- `source_slug`
- `title`
- `company`
- `raw_text_excerpt`
- `expected_skills`
- `expected_seniority`
- `expected_tech_stack`
- `expected_salary_band`
- `expected_remote_policy`
- `expected_role_archetype`
- `annotation_notes`

Use `split=train` for prompt tuning examples and `split=held_out` for regression scoring. The final Story 3.2 target remains 20 labeled postings with a fixed 10/10 train/held-out split.

