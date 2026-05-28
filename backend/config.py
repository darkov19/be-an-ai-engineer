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
    
    # Configure model config to resolve the environment file relative to the project structure
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
