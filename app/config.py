"""Application configuration."""
import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "DB Script Agent"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./db_script_agent.db"

    # LLM settings
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-3.5-turbo"
    llm_mock_mode: bool = True  # Use mock when no API key is set

    # Risk checker settings
    max_rows_without_where: int = 1000


settings = Settings()
