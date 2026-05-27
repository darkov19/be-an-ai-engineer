import time
import json
import traceback
import structlog
import httpx
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

logger = structlog.get_logger()

# =====================================================================
# HTML Tag Stripper
# =====================================================================

class HTMLTagStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'br', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.fed.append('\n')

    def handle_endtag(self, tag):
        if tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.fed.append('\n')

    def get_data(self) -> str:
        return ''.join(self.fed)


def strip_html(html_content: str) -> str:
    """
    Cleans HTML tags using standard library HTMLParser and returns clean text
    with preserved newlines, avoiding beautifulsoup4.
    """
    if not html_content:
        return ""
    stripper = HTMLTagStripper()
    stripper.feed(html_content)
    text = stripper.get_data()
    
    # Process lines: split by line breaks, strip each line
    lines = [line.strip() for line in text.split('\n')]
    
    # Filter out empty lines completely to keep it clean and single-newline separated
    non_empty_lines = [line for line in lines if line]
                
    return "\n".join(non_empty_lines)


# =====================================================================
# Secure XML Parser (Harden xml.etree.ElementTree against XXE / DTD expansion)
# =====================================================================

def parse_xml_safely(xml_content: str) -> ET.Element:
    """
    Parses XML string safely with DTD and entity validation using pyexpat.
    """
    import xml.parsers.expat
    
    def handle_entity_decl(entityName, is_parameter_entity, value, base, systemId, publicId, notationName):
        raise ValueError("XML entity declarations are forbidden for security reasons.")
        
    def handle_external_entity_ref(context, base, systemId, publicId):
        raise ValueError("XML external entity references are forbidden for security reasons.")
        
    def handle_start_doctype_decl(name, sysid, pubid, has_internal_subset):
        raise ValueError("DTD processing is forbidden for security reasons.")
        
    # Validate the XML content for DTD/Entity declarations using expat
    parser = xml.parsers.expat.ParserCreate()
    parser.EntityDeclHandler = handle_entity_decl
    parser.ExternalEntityRefHandler = handle_external_entity_ref
    parser.StartDoctypeDeclHandler = handle_start_doctype_decl
    
    try:
        parser.Parse(xml_content, True)
    except ValueError as ve:
        raise ve
    except xml.parsers.expat.ExpatError:
        # Non-security parse errors: let ElementTree attempt to parse with its own error handling
        pass
        
    # Once validated, parse it using standard ElementTree
    return ET.fromstring(xml_content)


# =====================================================================
# Parser Adapters
# =====================================================================

async def fetch_greenhouse_jobs(company_slug: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        absolute_url = job.get("absolute_url", "")
        company = company_slug.capitalize()
        
        loc_dict = job.get("location")
        location = loc_dict.get("name") if loc_dict else None
        
        raw_text = strip_html(job.get("content", ""))
        
        jobs.append({
            "url": absolute_url,
            "title": title,
            "company": company,
            "location": location,
            "raw_text": raw_text,
            "source_slug": "greenhouse"
        })
    return jobs


async def fetch_lever_jobs(company_slug: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    jobs = []
    for item in data:
        title = item.get("title", "")
        hosted_url = item.get("hostedUrl", "")
        company = company_slug.capitalize()
        
        categories = item.get("categories", {})
        location = categories.get("location")
        
        # Combine description, lists, and additional sections
        desc_html = item.get("description", "")
        lists_html = ""
        for section in item.get("lists", []):
            section_title = section.get("text", "")
            section_content = section.get("content", "")
            lists_html += f"<h3>{section_title}</h3>{section_content}"
        additional_html = item.get("additional", "")
        
        full_html = f"{desc_html}\n{lists_html}\n{additional_html}"
        raw_text = strip_html(full_html)
        
        jobs.append({
            "url": hosted_url,
            "title": title,
            "company": company,
            "location": location,
            "raw_text": raw_text,
            "source_slug": "lever"
        })
    return jobs


async def fetch_ashby_jobs(company_slug: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        job_url = job.get("jobUrl", "")
        company = company_slug.capitalize()
        location = job.get("location")
        raw_text = strip_html(job.get("descriptionHtml", ""))
        
        jobs.append({
            "url": job_url,
            "title": title,
            "company": company,
            "location": location,
            "raw_text": raw_text,
            "source_slug": "ashby"
        })
    return jobs


async def fetch_workable_jobs(company_slug: str) -> list[dict]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
        jobs = []
        for job in data.get("jobs", []):
            shortcode = job.get("shortcode", "")
            title = job.get("title", "")
            
            loc_data = job.get("location", {})
            if isinstance(loc_data, dict):
                city = loc_data.get("city")
                country = loc_data.get("country")
                location = f"{city}, {country}" if city and country else (city or country or None)
            else:
                location = str(loc_data)
                
            job_url = f"https://apply.workable.com/{company_slug}/j/{shortcode}/"
            
            description = job.get("description", "")
            if not description or len(description.strip()) < 100:
                try:
                    detail_url = f"https://apply.workable.com/api/v1/widget/jobs/{shortcode}"
                    detail_response = await client.get(detail_url)
                    detail_response.raise_for_status()
                    detail_data = detail_response.json()
                    
                    desc = detail_data.get("description", "")
                    reqs = detail_data.get("requirements", "")
                    benefits = detail_data.get("benefits", "")
                    full_desc = f"{desc}\n{reqs}\n{benefits}"
                    description = full_desc
                except Exception:
                    pass
                    
            raw_text = strip_html(description)
            
            jobs.append({
                "url": job_url,
                "title": title,
                "company": company_slug.capitalize(),
                "location": location,
                "raw_text": raw_text,
                "source_slug": "workable"
            })
    return jobs


async def fetch_recruitee_jobs(company_slug: str) -> list[dict]:
    url = f"https://{company_slug}.recruitee.com/api/offers"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    jobs = []
    for offer in data.get("offers", []):
        title = offer.get("title", "")
        careers_url = offer.get("careers_url", "")
        location = offer.get("location")
        
        desc = offer.get("description", "")
        reqs = offer.get("requirements", "")
        full_html = f"{desc}\n{reqs}"
        raw_text = strip_html(full_html)
        
        jobs.append({
            "url": careers_url,
            "title": title,
            "company": company_slug.capitalize(),
            "location": location,
            "raw_text": raw_text,
            "source_slug": "recruitee"
        })
    return jobs


async def fetch_personio_jobs(company_slug: str) -> list[dict]:
    url = f"https://{company_slug}.jobs.personio.de/xml?language=en"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            url = f"https://{company_slug}.jobs.personio.com/xml?language=en"
            response = await client.get(url)
            response.raise_for_status()
        xml_text = response.text
        
    root = parse_xml_safely(xml_text)
    
    jobs = []
    for position in root.findall(".//position"):
        pos_id = position.findtext("id", "")
        title = position.findtext("title", "")
        location = position.findtext("office", "")
        
        desc_parts = []
        for desc in position.findall(".//jobDescription"):
            name = desc.findtext("name", "")
            value = desc.findtext("value", "")
            if value:
                if name:
                    desc_parts.append(f"<h3>{name}</h3>{value}")
                else:
                    desc_parts.append(value)
                    
        if not desc_parts:
            html_desc = position.findtext("htmlDescription", "")
            if html_desc:
                desc_parts.append(html_desc)
            else:
                desc = position.findtext("description", "")
                if desc:
                    desc_parts.append(desc)
                    
        full_html = "\n".join(desc_parts)
        raw_text = strip_html(full_html)
        
        job_url = f"https://{company_slug}.jobs.personio.de/job/{pos_id}"
        
        jobs.append({
            "url": job_url,
            "title": title,
            "company": company_slug.capitalize(),
            "location": location,
            "raw_text": raw_text,
            "source_slug": "personio"
        })
    return jobs


async def fetch_yc_waas_jobs() -> list[dict]:
    """
    Mock parser simulating workatastartup.com API outputs for local testing.
    """
    return [
        {
            "url": "https://www.workatastartup.com/jobs/cognitiveflow-ai-app-engineer",
            "title": "AI Application Engineer",
            "company": "CognitiveFlow",
            "location": "San Francisco, CA",
            "raw_text": "We are looking for an AI Application Engineer to join our team. Tech stack: FastAPI, React, pgvector, RAG, Claude 3.5 Sonnet.",
            "source_slug": "yc_waas"
        },
        {
            "url": "https://www.workatastartup.com/jobs/sentientlabs-agent-systems-architect",
            "title": "Agent Systems Architect",
            "company": "SentientLabs",
            "location": "Remote US/EU",
            "raw_text": "We are seeking an Agent Systems Architect. Tech stack: LangGraph, Python, Vector DBs, Multi-Agent Systems.",
            "source_slug": "yc_waas"
        },
        {
            "url": "https://www.workatastartup.com/jobs/neuralscale-ml-platform-developer",
            "title": "ML Platform Developer",
            "company": "NeuralScale",
            "location": "Bengaluru, India",
            "raw_text": "Looking for an ML Platform Developer. Tech stack: PyTorch, CUDA, Docker, Kubernetes, Triton Inference Server.",
            "source_slug": "yc_waas"
        }
    ]


async def fetch_hn_jobs() -> list[dict]:
    """
    Fetches job postings from the latest monthly Ask HN thread on Hacker News via Algolia.
    Uses author_whoishiring tag filter so only the official thread is returned — no pagination needed.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={
                "query": '"Ask HN: Who is hiring"',
                "tags": "story,author_whoishiring",  # pre-filters to only whoishiring's posts
                "hitsPerPage": 1                     # most recent thread is always first
            }
        )
        response.raise_for_status()
        search_data = response.json()

        hits = search_data.get("hits", [])
        if not hits:
            raise ValueError("Could not find latest 'Ask HN: Who is hiring' thread via Algolia")

        thread_id = hits[0].get("objectID")

        items_url = f"https://hn.algolia.com/api/v1/items/{thread_id}"
        item_response = await client.get(items_url)
        item_response.raise_for_status()
        item_data = item_response.json()

    keywords = [
        "ai", "llm", "rag", "agent", "machine learning", 
        "deep learning", "transformer", "vector", "embeddings", 
        "neural", "pytorch"
    ]
    
    jobs = []
    for comment in item_data.get("children", []):
        text = comment.get("text")
        if not text:
            continue
            
        text_lower = text.lower()
        if not any(kw in text_lower for kw in keywords):
            continue
            
        comment_id = comment.get("id")
        author = comment.get("author", "anonymous")
        url = f"https://news.ycombinator.com/item?id={comment_id}"
        
        raw_text = strip_html(text)
        
        # Try to extract company name and location from the first line
        company = "Hacker News Comment"
        location = None
        
        first_line = raw_text.split("\n")[0] if raw_text else ""
        if first_line:
            parts = [p.strip() for p in first_line.split("|")]
            if len(parts) >= 1 and len(parts[0]) < 50:
                company = parts[0]
            if len(parts) >= 3 and len(parts[2]) < 50:
                location = parts[2]
            elif len(parts) >= 2 and len(parts[1]) < 50:
                location = parts[1]
                
        jobs.append({
            "url": url,
            "title": f"HN Hiring Comment by {author}",
            "company": company,
            "location": location,
            "raw_text": raw_text,
            "source_slug": "hn"
        })
    return jobs


# =====================================================================
# Database Integration and Orchestration
# =====================================================================

async def insert_job(conn, job: dict):
    """
    Safely inserts a job posting to the database, ensuring parameterized values
    to avoid SQL injection and handling duplicates using ON CONFLICT DO NOTHING.
    """
    required_keys = {"url", "title", "company", "raw_text", "source_slug"}
    missing = required_keys - job.keys()
    if missing:
        raise ValueError(f"Job dict missing required keys: {missing}")
    await conn.execute("""
        INSERT INTO jobs (url, title, company, location, raw_text, source_slug, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'backlog')
        ON CONFLICT (url) DO NOTHING
    """, (
        job["url"],
        job["title"],
        job["company"],
        job["location"],
        job["raw_text"],
        job["source_slug"]
    ))


async def run_full_ingestion(pool, config: dict = None) -> dict:
    """
    Orchestrates the full multi-source ingestion run.
    """
    if config is None:
        # Default simple set of slugs to test
        config = {
            "greenhouse": ["cockroach"],
            "lever": ["lever"],
            "ashby": ["sentry"],
            "workable": [],
            "recruitee": [],
            "personio": []
        }
        
    start_time = time.perf_counter()
    source_counts = {}
    errors = []
    successful_sources = 0
    all_jobs = []
    
    # 1. Greenhouse
    for slug in config.get("greenhouse", []):
        t0 = time.perf_counter()
        logger.info("Starting source ingestion", source_slug="greenhouse", company_slug=slug)
        try:
            jobs = await fetch_greenhouse_jobs(slug)
            all_jobs.extend(jobs)
            count = len(jobs)
            source_counts["greenhouse"] = source_counts.get("greenhouse", 0) + count
            successful_sources += 1
            logger.info("Source ingestion complete", source_slug="greenhouse", company_slug=slug, count=count, duration_seconds=time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"Greenhouse ({slug}): {str(e)}")
            logger.error("Source ingestion failed", source_slug="greenhouse", company_slug=slug, error=str(e), duration_seconds=time.perf_counter() - t0)
            
    # 2. Lever
    for slug in config.get("lever", []):
        t0 = time.perf_counter()
        logger.info("Starting source ingestion", source_slug="lever", company_slug=slug)
        try:
            jobs = await fetch_lever_jobs(slug)
            all_jobs.extend(jobs)
            count = len(jobs)
            source_counts["lever"] = source_counts.get("lever", 0) + count
            successful_sources += 1
            logger.info("Source ingestion complete", source_slug="lever", company_slug=slug, count=count, duration_seconds=time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"Lever ({slug}): {str(e)}")
            logger.error("Source ingestion failed", source_slug="lever", company_slug=slug, error=str(e), duration_seconds=time.perf_counter() - t0)
            
    # 3. Ashby
    for slug in config.get("ashby", []):
        t0 = time.perf_counter()
        logger.info("Starting source ingestion", source_slug="ashby", company_slug=slug)
        try:
            jobs = await fetch_ashby_jobs(slug)
            all_jobs.extend(jobs)
            count = len(jobs)
            source_counts["ashby"] = source_counts.get("ashby", 0) + count
            successful_sources += 1
            logger.info("Source ingestion complete", source_slug="ashby", company_slug=slug, count=count, duration_seconds=time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"Ashby ({slug}): {str(e)}")
            logger.error("Source ingestion failed", source_slug="ashby", company_slug=slug, error=str(e), duration_seconds=time.perf_counter() - t0)
            
    # 4. Workable
    for slug in config.get("workable", []):
        t0 = time.perf_counter()
        logger.info("Starting source ingestion", source_slug="workable", company_slug=slug)
        try:
            jobs = await fetch_workable_jobs(slug)
            all_jobs.extend(jobs)
            count = len(jobs)
            source_counts["workable"] = source_counts.get("workable", 0) + count
            successful_sources += 1
            logger.info("Source ingestion complete", source_slug="workable", company_slug=slug, count=count, duration_seconds=time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"Workable ({slug}): {str(e)}")
            logger.error("Source ingestion failed", source_slug="workable", company_slug=slug, error=str(e), duration_seconds=time.perf_counter() - t0)
            
    # 5. Recruitee
    for slug in config.get("recruitee", []):
        t0 = time.perf_counter()
        logger.info("Starting source ingestion", source_slug="recruitee", company_slug=slug)
        try:
            jobs = await fetch_recruitee_jobs(slug)
            all_jobs.extend(jobs)
            count = len(jobs)
            source_counts["recruitee"] = source_counts.get("recruitee", 0) + count
            successful_sources += 1
            logger.info("Source ingestion complete", source_slug="recruitee", company_slug=slug, count=count, duration_seconds=time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"Recruitee ({slug}): {str(e)}")
            logger.error("Source ingestion failed", source_slug="recruitee", company_slug=slug, error=str(e), duration_seconds=time.perf_counter() - t0)
            
    # 6. Personio
    for slug in config.get("personio", []):
        t0 = time.perf_counter()
        logger.info("Starting source ingestion", source_slug="personio", company_slug=slug)
        try:
            jobs = await fetch_personio_jobs(slug)
            all_jobs.extend(jobs)
            count = len(jobs)
            source_counts["personio"] = source_counts.get("personio", 0) + count
            successful_sources += 1
            logger.info("Source ingestion complete", source_slug="personio", company_slug=slug, count=count, duration_seconds=time.perf_counter() - t0)
        except Exception as e:
            errors.append(f"Personio ({slug}): {str(e)}")
            logger.error("Source ingestion failed", source_slug="personio", company_slug=slug, error=str(e), duration_seconds=time.perf_counter() - t0)
            
    # 7. YC WaaS
    t0 = time.perf_counter()
    logger.info("Starting source ingestion", source_slug="yc_waas", company_slug="none")
    try:
        jobs = await fetch_yc_waas_jobs()
        all_jobs.extend(jobs)
        count = len(jobs)
        source_counts["yc_waas"] = count
        successful_sources += 1
        logger.info("Source ingestion complete", source_slug="yc_waas", company_slug="none", count=count, duration_seconds=time.perf_counter() - t0)
    except Exception as e:
        errors.append(f"YC WaaS: {str(e)}")
        logger.error("Source ingestion failed", source_slug="yc_waas", company_slug="none", error=str(e), duration_seconds=time.perf_counter() - t0)
        
    # 8. Hacker News
    t0 = time.perf_counter()
    logger.info("Starting source ingestion", source_slug="hn", company_slug="none")
    try:
        jobs = await fetch_hn_jobs()
        all_jobs.extend(jobs)
        count = len(jobs)
        source_counts["hn"] = count
        successful_sources += 1
        logger.info("Source ingestion complete", source_slug="hn", company_slug="none", count=count, duration_seconds=time.perf_counter() - t0)
    except Exception as e:
        errors.append(f"HN: {str(e)}")
        logger.error("Source ingestion failed", source_slug="hn", company_slug="none", error=str(e), duration_seconds=time.perf_counter() - t0)
        
    # Fill in missing counts
    for source in ["greenhouse", "lever", "ashby", "workable", "recruitee", "personio", "yc_waas", "hn"]:
        if source not in source_counts:
            source_counts[source] = 0
            
    # Write to database
    db_error = None
    if all_jobs:
        try:
            async with pool.connection() as conn:
                async with conn.transaction():
                    for job in all_jobs:
                        await insert_job(conn, job)
        except Exception as e:
            db_error = f"Database insertion failed: {str(e)}"
            errors.append(db_error)
            logger.error("Database jobs insertion failed", error=str(e))
            
    # Determine overall status: success if at least one source parsed without error
    if successful_sources > 0:
        run_status = "success"
    else:
        run_status = "failure"
        
    execution_time = time.perf_counter() - start_time
    error_msg = "; ".join(errors) if errors else None
    
    # Save the ingestion run metadata
    try:
        async with pool.connection() as conn:
            await conn.execute("""
                INSERT INTO ingestion_runs (status, source_counts, error_message, execution_time_seconds)
                VALUES (%s, %s, %s, %s)
            """, (
                run_status,
                json.dumps(source_counts),
                error_msg,
                execution_time
            ))
    except Exception as e:
        logger.error("Failed to save ingestion run metadata", error=str(e))
        
    return {
        "status": run_status,
        "source_counts": source_counts,
        "error_message": error_msg,
        "execution_time_seconds": execution_time
    }
