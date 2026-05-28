import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # No default: forces explicit configuration via .env.
    # Pydantic will raise a ValidationError at startup if DATABASE_URL is absent,
    # preventing the app from silently running with embedded credentials.
    database_url: str
    resend_api_key: str | None = None
    alert_recipient_email: str = "onboarding@resend.dev"
    hermes_host: str = "127.0.0.1"
    hermes_port: int = 3000
    vertex_search_enabled: bool = False
    vertex_search_prod_mode: bool = False
    vertex_search_api_key: str | None = None
    vertex_search_project_id: str | None = None
    vertex_search_location: str = "global"
    vertex_search_engine_id: str | None = None
    vertex_search_serving_config_id: str = "default_search"
    vertex_search_quota_state_file: str | None = None
    vertex_search_test_monthly_cap: int = 100
    vertex_search_test_daily_cap: int = 10
    vertex_search_test_max_queries_per_run: int = 3
    vertex_search_prod_monthly_cap: int = 8000
    vertex_search_prod_daily_cap: int = 300
    vertex_search_prod_max_queries_per_run: int = 100
    wellfound_discovery_enabled: bool = False
    wellfound_import_file: str | None = None
    wellfound_auto_extract_enabled: bool = False
    wellfound_max_pages_per_run: int = 5
    wellfound_request_delay_seconds: float = 5.0
    common_crawl_discovery_enabled: bool = False
    common_crawl_crawl_ids: str | None = None
    common_crawl_max_crawls: int = 1
    common_crawl_max_records_per_pattern: int = 25
    common_crawl_total_record_cap: int = 100
    common_crawl_request_timeout_seconds: float = 5.0
    common_crawl_request_delay_seconds: float = 1.0
    common_crawl_max_response_bytes: int = 500_000
    yc_company_discovery_enabled: bool = False
    yc_company_categories: str = "ai,developer-tools,infrastructure,data-engineering,databases,open-source,search"
    yc_company_import_file: str | None = None
    yc_company_max_companies_per_category: int = 25
    yc_company_max_total_companies: int = 100
    yc_company_request_timeout_seconds: float = 5.0
    yc_company_max_response_bytes: int = 500_000
    vc_portfolio_discovery_enabled: bool = False
    vc_portfolio_import_file: str | None = None
    vc_portfolio_targets_json: str | None = None
    vc_portfolio_max_companies_per_target: int = 50
    vc_portfolio_request_timeout_seconds: float = 5.0
    vc_portfolio_max_response_bytes: int = 500_000
    github_org_discovery_enabled: bool = False
    github_org_token: str | None = None
    github_org_topics: str = "llm,rag,vector-database,mlops,agents,fastapi,developer-tools,data-platform,evals"
    github_org_queries: str = "llm,rag,vector-database,mlops,agents,fastapi,developer-tools,data-platform,evals"
    github_org_max_search_queries: int = 6
    github_org_max_pages_per_query: int = 1
    github_org_max_repos_per_query: int = 10
    github_org_max_orgs_per_run: int = 25
    github_org_max_organization_metadata_fetches: int = 10
    github_org_max_readme_fetches_per_run: int = 10
    github_org_request_timeout_seconds: float = 5.0
    github_org_request_delay_seconds: float = 1.0
    github_org_max_response_bytes: int = 500_000
    reddit_hiring_discovery_enabled: bool = False
    reddit_hiring_client_id: str | None = None
    reddit_hiring_client_secret: str | None = None
    reddit_hiring_access_token: str | None = None
    reddit_hiring_user_agent: str = "be-an-ai-engineer-source-discovery/1.0"
    reddit_hiring_allow_unauthenticated: bool = False
    reddit_hiring_subreddits: str = "MachineLearningJobs,PythonJobs,forhire,remotepython"
    reddit_hiring_search_terms: str = "hiring,AI Engineer,LLM,RAG,Python,FastAPI,backend,remote"
    reddit_hiring_max_pages_per_query: int = 1
    reddit_hiring_max_posts_per_query: int = 10
    reddit_hiring_max_posts_per_run: int = 50
    reddit_hiring_request_timeout_seconds: float = 5.0
    reddit_hiring_request_delay_seconds: float = 1.0
    reddit_hiring_max_response_bytes: int = 500_000
    reddit_hiring_default_confidence: float = 0.25
    reddit_hiring_strong_signal_confidence: float = 0.4
    discovery_stale_source_days: int = 30
    discovery_repeated_rejection_window_days: int = 30
    discovery_repeated_rejection_count: int = 3
    discovery_high_yield_min_validated_sources: int = 2
    discovery_max_company_signals_per_run: int = 250
    discovery_max_company_resolutions_per_run: int = 100
    
    # Configure model config to resolve the environment file relative to the project structure
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
