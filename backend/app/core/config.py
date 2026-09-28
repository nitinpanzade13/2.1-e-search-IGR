import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/esearch_igr"
    TEST_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/esearch_igr_test"
    SCRAPER_TEST_MODE: bool = True
    IGR_LIVE_TEST_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_CAPTCHA_MODEL: str = "gpt-4o"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
