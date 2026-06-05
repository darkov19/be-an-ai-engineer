import os
import re
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import httpx
import structlog
from psycopg.rows import dict_row

from backend.config import settings
from backend.llm.hermes import check_hermes_proxy_health

logger = structlog.get_logger()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{company_name} // Stack Fingerprint</title>
    <style>
        :root {{
            --bg-cosmic: #030303;
            --bg-panel: hsla(240, 16%, 2%, 0.7);
            --border-hud: hsla(180, 100%, 50%, 0.15);
            --glow-cyan: hsl(180, 100%, 50%);
            --glow-purple: hsl(270, 100%, 60%);
            --glow-magenta: hsl(325, 100%, 55%);
            --glow-green: hsl(145, 80%, 45%);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --font-sans: Outfit, Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-cosmic);
            color: var(--text-primary);
            font-family: var(--font-sans);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 100vh;
            padding: 24px;
        }}

        .hud-container {{
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border-hud);
            background: var(--bg-panel);
            padding: 24px;
            position: relative;
            box-shadow: 0 0 20px hsla(180, 100%, 50%, 0.05);
        }}

        .hud-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-hud);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}

        .logo-section {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo-symbol {{
            color: var(--glow-cyan);
            font-size: 1.5rem;
            text-shadow: 0 0 8px hsla(180, 100%, 50%, 0.5);
            animation: pulse 2s infinite;
        }}

        .logo-text {{
            font-size: 1.25rem;
            font-weight: 900;
            letter-spacing: 0.15em;
            color: var(--text-primary);
        }}

        .status-badge {{
            font-family: var(--font-mono);
            font-size: 0.8rem;
            color: var(--glow-green);
            text-shadow: 0 0 6px hsla(145, 80%, 45%, 0.3);
            border: 1px solid var(--glow-green);
            padding: 4px 8px;
            border-radius: 2px;
        }}

        .main-layout {{
            flex-grow: 1;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}

        .hud-panel {{
            border: 1px solid var(--border-hud);
            padding: 20px;
            background: hsla(240, 16%, 1%, 0.9);
            border-radius: 4px;
            position: relative;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .hud-panel.cyan {{
            border-left: 3px solid var(--glow-cyan);
            box-shadow: 0 0 10px hsla(180, 100%, 50%, 0.02);
        }}

        .hud-panel.purple {{
            border-left: 3px solid var(--glow-purple);
            box-shadow: 0 0 10px hsla(270, 100%, 60%, 0.02);
        }}

        .panel-title {{
            font-size: 0.9rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-hud);
            padding-bottom: 8px;
            text-transform: uppercase;
        }}

        .tech-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .tech-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            padding: 6px 8px;
            background: hsla(240, 10%, 4%, 0.6);
            border: 1px solid var(--border-hud);
            border-radius: 2px;
        }}

        .tech-name {{
            color: var(--text-primary);
            font-weight: bold;
        }}

        .tech-count {{
            color: var(--glow-cyan);
            text-shadow: 0 0 6px hsla(180, 100%, 50%, 0.3);
        }}

        .bullets-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .bullet-item {{
            display: flex;
            gap: 12px;
            font-size: 0.9rem;
            line-height: 1.4;
            color: var(--text-secondary);
        }}

        .bullet-marker {{
            color: var(--glow-purple);
            font-family: var(--font-mono);
            font-weight: bold;
        }}

        .observation-container {{
            margin-top: auto;
            border: 1px solid var(--border-hud);
            border-left: 3px solid var(--glow-magenta);
            padding: 16px;
            background: hsla(325, 100%, 55%, 0.02);
            border-radius: 4px;
        }}

        .observation-title {{
            font-size: 0.8rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            color: var(--glow-magenta);
            text-shadow: 0 0 6px hsla(325, 100%, 55%, 0.3);
            text-transform: uppercase;
            margin-bottom: 8px;
        }}

        .observation-text {{
            font-size: 0.95rem;
            line-height: 1.5;
            color: var(--text-primary);
        }}

        .hud-footer {{
            display: flex;
            justify-content: space-between;
            font-family: var(--font-mono);
            font-size: 0.7rem;
            color: var(--text-secondary);
            border-top: 1px solid var(--border-hud);
            padding-top: 12px;
            margin-top: 24px;
        }}

        .close-demo-btn {{
            display: none;
            background: transparent;
            color: var(--glow-magenta);
            border: 1px solid var(--glow-magenta);
            padding: 6px 16px;
            font-family: var(--font-sans);
            font-size: 0.85rem;
            font-weight: bold;
            letter-spacing: 0.05em;
            cursor: pointer;
            border-radius: 2px;
            transition: all 0.2s ease;
        }}

        .close-demo-btn:hover {{
            background: var(--glow-magenta);
            color: var(--bg-cosmic);
            box-shadow: 0 0 12px hsla(325, 100%, 55%, 0.5);
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 0.6; }}
            50% {{ opacity: 1; }}
        }}
    </style>
</head>
<body>
    <div class="hud-container">
        <header class="hud-header">
            <div class="logo-section">
                <span class="logo-symbol">▲</span>
                <h1 class="logo-text">{company_name_upper} // STACK FINGERPRINT</h1>
            </div>
            <div>
                <button id="close-demo-btn" class="close-demo-btn" onclick="window.location.href='/'">[CLOSE DEMO]</button>
            </div>
            <div class="status-badge">OFFLINE_FALLBACK // LIVE</div>
        </header>

        <div class="main-layout">
            <section class="hud-panel cyan">
                <h2 class="panel-title">TOP 10 EXTRACTED TECHNOLOGIES</h2>
                <div class="tech-list">
                    {tech_list_html}
                </div>
            </section>

            <section class="hud-panel purple">
                <h2 class="panel-title">ROLE ARCHETYPE SUMMARY</h2>
                <div class="bullets-list">
                    {bullet_list_html}
                </div>
            </section>
        </div>

        <div class="observation-container">
            <h3 class="observation-title">AI Stack Observation</h3>
            <p class="observation-text">{llm_observation}</p>
        </div>

        <footer class="hud-footer">
            <span>FALLBACK CACHE GENERATED: {timestamp}</span>
            <span>VER: 1.2.0-HUD // PUBLIC_VIEW</span>
        </footer>
    </div>

    <script>
        const params = new URLSearchParams(window.location.search);
        if (params.get('demo') === 'true') {{
            document.getElementById('close-demo-btn').style.display = 'block';
        }}
    </script>
</body>
</html>
"""

async def generate_fingerprint_data(pool, company_slug: str) -> dict:
    """
    Aggregates extracted job postings for a company slug, queries Hermes proxy
    for summarized bullet points and stack observation, and updates company_fingerprints table.
    """
    if not re.fullmatch(r"[a-z0-9-]+", company_slug):
        raise ValueError("Invalid company slug format")

    # Resolve company variants and check job_sources table
    company_variants = [company_slug.replace("-", " "), company_slug.replace("_", " "), company_slug]
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT company FROM job_sources WHERE LOWER(slug) = LOWER(%s) LIMIT 1",
                    (company_slug,)
                )
                row = await cur.fetchone()
                if row and row[0]:
                    company_variants.append(row[0])
    except Exception as e:
        logger.warning("Failed to query job_sources for company variant", error=str(e))

    # Clean and deduplicate variants
    company_variants = list(set(v.lower().strip() for v in company_variants if v))

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT company, title, raw_text, skills, tech_stack, remote_policy, role_archetype
                FROM jobs
                WHERE LOWER(company) = ANY(%s)
                  AND extraction_status = 'extracted'
                """,
                (company_variants,)
            )
            jobs = await cur.fetchall()

    if not jobs:
        raise ValueError(f"No extracted job postings found for company: {company_slug}")

    # Establish canonical company capitalization
    company_name = company_slug.capitalize()
    cap_counts = {}
    for j in jobs:
        c = j.get("company")
        if c:
            cap_counts[c] = cap_counts.get(c, 0) + 1
    if cap_counts:
        company_name = max(cap_counts, key=cap_counts.get)

    # Compute top-10 technologies
    tech_counts = {}
    for j in jobs:
        stack = j.get("tech_stack")
        if isinstance(stack, list):
            for tech in stack:
                if isinstance(tech, str) and tech.strip():
                    t_clean = tech.strip()
                    tech_counts[t_clean] = tech_counts.get(t_clean, 0) + 1

    sorted_tech = sorted(tech_counts.items(), key=lambda x: (-x[1], x[0].lower()))
    top_tech = [{"name": name, "count": count} for name, count in sorted_tech[:10]]

    # Aggregate summaries for the LLM
    job_summaries = []
    for idx, j in enumerate(jobs):
        title = j.get("title") or "Job Post"
        skills = ", ".join(j.get("skills") or [])
        tech = ", ".join(j.get("tech_stack") or [])
        arch = j.get("role_archetype") or "unknown"
        job_summaries.append(
            f"Job #{idx+1}:\nTitle: {title}\nRole Archetype: {arch}\nSkills: {skills}\nTech Stack: {tech}"
        )
    jobs_summary_text = "\n\n".join(job_summaries)

    # Call Hermes for summary
    await check_hermes_proxy_health()

    prompt = f"""You are an expert AI and tech stack analyst for company profiles.
Analyze the job postings for {company_name} to generate:
1. A 5-bullet role archetype summary. Each bullet must be extremely concise, starting with a dash, and describe a hiring pattern or key role capability required by the company.
2. A one-sentence observation of their tech stack direction.

Your output must be a single JSON object matching this schema:
{{
  "role_archetypes": [
    "Bullet 1 (exactly 5 bullets required)",
    "Bullet 2",
    "Bullet 3",
    "Bullet 4",
    "Bullet 5"
  ],
  "llm_observation": "A single-sentence tech stack observation."
}}
Return only the raw JSON. Do not wrap in markdown blocks or include pre/post commentary.
"""

    payload = {
        "prompt_version": "company_summary_v1",
        "schema_version": "v1",
        "prompt": prompt,
        "jobs": [
            {
                "job_id": 1,
                "url": "http://internal/summary",
                "title": "Jobs Summary",
                "company": company_name,
                "location": "Remote",
                "source_slug": "summary",
                "raw_text": jobs_summary_text[:8000]
            }
        ]
    }

    url = f"http://{settings.hermes_host}:{settings.hermes_port}/extract"
    logger.info("Requesting company summary from Hermes proxy", company_slug=company_slug)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        res_data = response.json()

    llm_output = None
    if isinstance(res_data, dict):
        if "items" in res_data and isinstance(res_data["items"], list) and len(res_data["items"]) > 0:
            item = res_data["items"][0]
            if isinstance(item, dict):
                if "role_archetypes" in item or "llm_observation" in item:
                    llm_output = item
        
        if llm_output is None:
            if "role_archetypes" in res_data:
                llm_output = res_data
            else:
                for v in res_data.values():
                    if isinstance(v, str):
                        try:
                            parsed_v = json.loads(v)
                            if isinstance(parsed_v, dict) and "role_archetypes" in parsed_v:
                                llm_output = parsed_v
                                break
                        except Exception:
                            match = re.search(r"\{.*\}", v, re.DOTALL)
                            if match:
                                try:
                                    parsed_v = json.loads(match.group(0))
                                    if isinstance(parsed_v, dict) and "role_archetypes" in parsed_v:
                                        llm_output = parsed_v
                                        break
                                except Exception:
                                    pass

    role_archetypes = []
    llm_observation = ""
    if llm_output and isinstance(llm_output, dict):
        role_archetypes = llm_output.get("role_archetypes") or []
        llm_observation = llm_output.get("llm_observation") or ""

    if not isinstance(role_archetypes, list):
        role_archetypes = [str(role_archetypes)]
    role_archetypes = [b.strip().lstrip("- ").strip() for b in role_archetypes if b]
    while len(role_archetypes) < 5:
        role_archetypes.append("Hiring pattern: expansion of tech stack roles.")
    role_archetypes = role_archetypes[:5]

    if not llm_observation or not isinstance(llm_observation, str):
        llm_observation = f"{company_name} is actively building applications using {', '.join([t['name'] for t in top_tech[:3]])}."

    fingerprint_data = {
        "company_slug": company_slug,
        "company_name": company_name,
        "role_archetypes": role_archetypes,
        "top_technologies": top_tech,
        "llm_observation": llm_observation
    }

    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO company_fingerprints (company_slug, company_name, role_archetypes, top_technologies, llm_observation, updated_at)
                    VALUES (%(company_slug)s, %(company_name)s, %(role_archetypes)s::jsonb, %(top_technologies)s::jsonb, %(llm_observation)s, CURRENT_TIMESTAMP)
                    ON CONFLICT (company_slug)
                    DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        role_archetypes = EXCLUDED.role_archetypes,
                        top_technologies = EXCLUDED.top_technologies,
                        llm_observation = EXCLUDED.llm_observation,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    {
                        "company_slug": company_slug,
                        "company_name": company_name,
                        "role_archetypes": json.dumps(role_archetypes),
                        "top_technologies": json.dumps(top_tech),
                        "llm_observation": llm_observation
                    }
                )

    return fingerprint_data

def write_static_html(company_slug: str, fingerprint_data: dict):
    """
    Renders fingerprint data into static HTML template and caches it in public directory.
    Includes validation to prevent path traversal vulnerability.
    """
    safe_slug = os.path.basename(company_slug)
    if safe_slug != company_slug:
        raise ValueError("Invalid company slug (path traversal detected)")
    if not re.fullmatch(r"[a-z0-9-]+", safe_slug):
        raise ValueError("Invalid company slug format")

    workspace_root = Path(__file__).resolve().parents[2]
    output_dir = (workspace_root / "frontend" / "public" / "cached-fingerprints").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    target_path = (output_dir / f"{safe_slug}.html").resolve()
    try:
        target_path.relative_to(output_dir)
    except ValueError:
        raise ValueError("Path traversal detected")

    company_name = escape(str(fingerprint_data["company_name"]))
    company_name_upper = escape(str(fingerprint_data["company_name"]).upper())
    role_archetypes = fingerprint_data["role_archetypes"]
    top_tech = fingerprint_data["top_technologies"]
    llm_observation = escape(str(fingerprint_data["llm_observation"]))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    tech_rows_html = []
    for tech in top_tech:
        name = escape(str(tech["name"]))
        count = escape(str(tech["count"]))
        tech_rows_html.append(f"""
        <div class="tech-row">
            <span class="tech-name">{name}</span>
            <span class="tech-count">{count}</span>
        </div>
        """)
    tech_list_html = "\n".join(tech_rows_html)

    bullet_items_html = []
    for idx, bullet in enumerate(role_archetypes):
        bullet_text = escape(str(bullet))
        bullet_items_html.append(f"""
        <div class="bullet-item">
            <span class="bullet-marker">0{idx+1} //</span>
            <span>{bullet_text}</span>
        </div>
        """)
    bullet_list_html = "\n".join(bullet_items_html)

    html_content = HTML_TEMPLATE.format(
        company_name=company_name,
        company_name_upper=company_name_upper,
        tech_list_html=tech_list_html,
        bullet_list_html=bullet_list_html,
        llm_observation=llm_observation,
        timestamp=timestamp
    )

    target_path.write_text(html_content, encoding="utf-8")
    logger.info("Successfully wrote static HTML fallback cache", path=str(target_path))
