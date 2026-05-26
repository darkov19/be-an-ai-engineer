import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # No default: forces explicit configuration via .env.
    # Pydantic will raise a ValidationError at startup if DATABASE_URL is absent,
    # preventing the app from silently running with embedded credentials.
    database_url: str
    
    # Configure model config to resolve the environment file relative to the project structure
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
