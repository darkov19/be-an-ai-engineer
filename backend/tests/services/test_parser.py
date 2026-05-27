import pytest
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch
import json
import psycopg

from backend.services.parser import (
    strip_html,
    parse_xml_safely,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_ashby_jobs,
    fetch_workable_jobs,
    fetch_recruitee_jobs,
    fetch_personio_jobs,
    fetch_yc_waas_jobs,
    fetch_hn_jobs,
    insert_job,
    run_full_ingestion
)

# =====================================================================
# Unit Tests: HTML Tag Stripper
# =====================================================================

def test_strip_html_basic():
    html = "<p>Hello <b>World</b></p><br/>Welcome to the <a href='https://google.com'>search</a>."
    expected = "Hello World\nWelcome to the search."
    assert strip_html(html) == expected


def test_strip_html_block_newlines():
    html = "<div>Line 1</div><p>Line 2</p>Line 3<br>Line 4"
    expected = "Line 1\nLine 2\nLine 3\nLine 4"
    assert strip_html(html) == expected


def test_strip_html_whitespace_collapse():
    html = "   <p>   Some   text   </p>   \n\n\n   <p>More text</p>  "
    expected = "Some   text\nMore text"
    assert strip_html(html) == expected


# =====================================================================
# Unit Tests: XML Parsing Security
# =====================================================================

def test_xml_security_billion_laughs():
    billion_laughs_xml = """<?xml version="1.0"?>
    <!DOCTYPE lolz [
     <!ENTITY lol "lol">
     <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
    ]>
    <workpositions>
      <position>
        <id>1</id>
        <title>&lol2;</title>
      </position>
    </workpositions>"""
    
    with pytest.raises(ValueError, match="DTD processing is forbidden|Entity declarations are forbidden"):
        parse_xml_safely(billion_laughs_xml)


def test_xml_security_xxe():
    xxe_xml = """<?xml version="1.0"?>
    <!DOCTYPE test [
     <!ENTITY xxe SYSTEM "http://localhost:9999/xxe.txt">
    ]>
    <workpositions>
      <position>
        <id>1</id>
        <title>&xxe;</title>
      </position>
    </workpositions>"""
    
    with pytest.raises(ValueError, match="DTD processing is forbidden|XML external entity references are forbidden"):
        parse_xml_safely(xxe_xml)


# =====================================================================
# Mock HTTP client responses helper
# =====================================================================

class MockResponse:
    def __init__(self, json_data=None, text_data=None, status_code=200):
        self._json = json_data
        self._text = text_data
        self.status_code = status_code
        
    def json(self):
        return self._json
        
    @property
    def text(self):
        return self._text
        
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code}")


# =====================================================================
# Mocked Integrations: Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, HN
# =====================================================================

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_greenhouse_jobs(mock_get):
    mock_get.return_value = MockResponse(json_data={
        "jobs": [
            {
                "id": 123,
                "title": "AI Engineer",
                "location": {"name": "San Francisco, CA"},
                "content": "<p>We do cool AI stuff.</p>",
                "absolute_url": "https://boards.greenhouse.io/test/jobs/123"
            }
        ]
    })
    
    jobs = await fetch_greenhouse_jobs("test")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI Engineer"
    assert jobs[0]["company"] == "Test"
    assert jobs[0]["location"] == "San Francisco, CA"
    assert jobs[0]["raw_text"] == "We do cool AI stuff."
    assert jobs[0]["source_slug"] == "greenhouse"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_lever_jobs(mock_get):
    mock_get.return_value = MockResponse(json_data=[
        {
            "id": "lever-123",
            "title": "Machine Learning Engineer",
            "categories": {"location": "Remote"},
            "description": "<p>Main description.</p>",
            "lists": [
                {"text": "Requirements", "content": "<ul><li>Python</li></ul>"}
            ],
            "additional": "<p>Some extras.</p>",
            "hostedUrl": "https://jobs.lever.co/test/lever-123"
        }
    ])
    
    jobs = await fetch_lever_jobs("test")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Machine Learning Engineer"
    assert jobs[0]["company"] == "Test"
    assert jobs[0]["location"] == "Remote"
    assert "Main description." in jobs[0]["raw_text"]
    assert "Requirements" in jobs[0]["raw_text"]
    assert "Python" in jobs[0]["raw_text"]
    assert "Some extras." in jobs[0]["raw_text"]
    assert jobs[0]["source_slug"] == "lever"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_ashby_jobs(mock_get):
    mock_get.return_value = MockResponse(json_data={
        "jobs": [
            {
                "id": "ashby-1",
                "title": "RAG Specialist",
                "location": "New York",
                "descriptionHtml": "<div>FastAPI and RAG stack.</div>",
                "jobUrl": "https://jobs.ashbyhq.com/test/ashby-1"
            }
        ]
    })
    
    jobs = await fetch_ashby_jobs("test")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "RAG Specialist"
    assert jobs[0]["location"] == "New York"
    assert jobs[0]["raw_text"] == "FastAPI and RAG stack."
    assert jobs[0]["source_slug"] == "ashby"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_workable_jobs_with_details_fetch(mock_get):
    # Setup mock to return summary first, then details
    summary_resp = MockResponse(json_data={
        "jobs": [
            {
                "shortcode": "workable-1",
                "title": "LLM Engineer",
                "location": {"city": "Boston", "country": "US"},
                "description": "" # Empty description to trigger detail fetch
            }
        ]
    })
    
    detail_resp = MockResponse(json_data={
        "description": "<p>Deep learning description</p>",
        "requirements": "<p>PhD in ML</p>",
        "benefits": "<p>Free lunch</p>"
    })
    
    mock_get.side_effect = [summary_resp, detail_resp]
    
    jobs = await fetch_workable_jobs("test")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "LLM Engineer"
    assert jobs[0]["location"] == "Boston, US"
    assert "Deep learning description" in jobs[0]["raw_text"]
    assert "PhD in ML" in jobs[0]["raw_text"]
    assert "Free lunch" in jobs[0]["raw_text"]
    assert jobs[0]["source_slug"] == "workable"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_recruitee_jobs(mock_get):
    mock_get.return_value = MockResponse(json_data={
        "offers": [
            {
                "id": 999,
                "title": "Agent Architect",
                "location": "Amsterdam",
                "description": "<p>Agentic workflows</p>",
                "requirements": "<p>LangGraph skills</p>",
                "careers_url": "https://test.recruitee.com/o/agent-architect"
            }
        ]
    })
    
    jobs = await fetch_recruitee_jobs("test")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Agent Architect"
    assert jobs[0]["location"] == "Amsterdam"
    assert "Agentic workflows" in jobs[0]["raw_text"]
    assert "LangGraph skills" in jobs[0]["raw_text"]
    assert jobs[0]["source_slug"] == "recruitee"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_personio_jobs(mock_get):
    xml_data = """<?xml version="1.0" encoding="utf-8"?>
    <workpositions>
      <position>
        <id>p-1</id>
        <title><![CDATA[Python Developer]]></title>
        <office><![CDATA[Munich]]></office>
        <jobDescriptions>
          <jobDescription>
            <name><![CDATA[Role]]></name>
            <value><![CDATA[<p>FastAPI Backend</p>]]></value>
          </jobDescription>
        </jobDescriptions>
      </position>
    </workpositions>"""
    
    mock_get.return_value = MockResponse(text_data=xml_data)
    
    jobs = await fetch_personio_jobs("test")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Python Developer"
    assert jobs[0]["location"] == "Munich"
    assert "FastAPI Backend" in jobs[0]["raw_text"]
    assert jobs[0]["source_slug"] == "personio"


@pytest.mark.asyncio
async def test_fetch_yc_waas_jobs():
    jobs = await fetch_yc_waas_jobs()
    assert len(jobs) == 3
    assert jobs[0]["company"] == "CognitiveFlow"
    assert jobs[1]["company"] == "SentientLabs"
    assert jobs[2]["company"] == "NeuralScale"


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_hn_jobs(mock_get):
    search_resp = MockResponse(json_data={
        "hits": [
            {
                "author": "whoishiring",
                "title": "Ask HN: Who is hiring? (May 2026)",
                "objectID": "hn-thread-1"
            }
        ]
    })
    
    thread_resp = MockResponse(json_data={
        "children": [
            {
                "id": 10001,
                "author": "company_rep",
                "text": "<p>CognitiveFlow | AI Engineer | San Francisco, CA | Full-Time | ONSITE<br>We build cool Agent systems using LangGraph.</p>"
            },
            {
                "id": 10002,
                "author": "irrelevant_rep",
                "text": "<p>TraditionalCorp | PHP Developer | London, UK | Onsite<br>We do old legacy stuff (not a-i keyword matching).</p>"
            }
        ]
    })
    
    mock_get.side_effect = [search_resp, thread_resp]
    
    jobs = await fetch_hn_jobs()
    assert len(jobs) == 1  # Only the AI one passes the keyword filter
    assert jobs[0]["company"] == "CognitiveFlow"
    assert jobs[0]["location"] == "San Francisco, CA"
    assert "Agent systems using LangGraph" in jobs[0]["raw_text"]
    assert jobs[0]["source_slug"] == "hn"


# =====================================================================
# Database Insertion and Orchestration Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_insert_job_and_duplicate_skipping():
    # Mock psycopg AsyncConnection
    mock_conn = AsyncMock()
    
    job = {
        "url": "https://jobs.example.com/1",
        "title": "Senior AI Developer",
        "company": "SmartTech",
        "location": "Boston",
        "raw_text": "Requirements: Python, PyTorch, pgvector.",
        "source_slug": "greenhouse"
    }
    
    await insert_job(mock_conn, job)
    
    # Assert query was executed with correct parameterization
    mock_conn.execute.assert_called_once()
    args, kwargs = mock_conn.execute.call_args
    assert "INSERT INTO jobs" in args[0]
    assert "ON CONFLICT (url) DO NOTHING" in args[0]
    assert args[1][0] == job["url"]
    assert args[1][1] == job["title"]
    assert args[1][2] == job["company"]
    assert args[1][3] == job["location"]
    assert args[1][4] == job["raw_text"]
    assert args[1][5] == job["source_slug"]


@pytest.mark.asyncio
@patch("backend.services.parser.fetch_greenhouse_jobs")
@patch("backend.services.parser.fetch_yc_waas_jobs")
@patch("backend.services.parser.fetch_hn_jobs")
async def test_run_full_ingestion_success(mock_hn, mock_yc, mock_greenhouse):
    mock_greenhouse.return_value = [{"url": "url-1", "title": "Job 1", "company": "Company 1", "location": "NYC", "raw_text": "Description 1", "source_slug": "greenhouse"}]
    mock_yc.return_value = [{"url": "url-2", "title": "Job 2", "company": "Company 2", "location": "SF", "raw_text": "Description 2", "source_slug": "yc_waas"}]
    mock_hn.return_value = []
    
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock()
    mock_conn.transaction.return_value = AsyncMock()
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
    
    config = {
        "greenhouse": ["company1"],
        "lever": [],
        "ashby": [],
        "workable": [],
        "recruitee": [],
        "personio": []
    }
    
    results = await run_full_ingestion(mock_pool, config)
    
    assert results["status"] == "success"
    assert results["source_counts"]["greenhouse"] == 1
    assert results["source_counts"]["yc_waas"] == 1
    assert results["source_counts"]["hn"] == 0
    assert results["error_message"] is None
    
    # Ensure insert_job was called for jobs
    assert mock_conn.execute.call_count >= 3  # (2 jobs inserts + 1 ingestion run log insert)
