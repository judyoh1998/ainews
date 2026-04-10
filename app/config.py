from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_path: str = "data/neko.db"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72
    default_cadence: str = "daily"
    default_timezone: str = "UTC"
    max_newsletter_size: int = 500_000
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_max_retries: int = 3
    llm_timeout: int = 120

    model_config = {"env_prefix": "NEKO_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
