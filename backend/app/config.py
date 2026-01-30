from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # API Keys
    openai_api_key: str = ""
    groq_api_key: str = ""
    # OpenAI-compatible base URL (e.g., LM Studio)
    openai_base_url: str = "http://localhost:1234/v1"
    
    # Database
    database_url: str = "postgresql://localhost:5432/ayush_habba"
    
    # Model Configuration
    planner_model: str = "mistralai/ministral-3-3b"  # High-intelligence for planning
    executor_model: str = "mistralai/ministral-3-3b"  # Cost-effective for execution
    
    # Application
    app_name: str = "Ayush Habba"
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
