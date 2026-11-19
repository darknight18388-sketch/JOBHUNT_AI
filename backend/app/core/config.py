from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://jobhunt:change_me@localhost:5432/jobhunt"
    ai_provider: str = "ollama"
    ai_api_key: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    jwt_secret: str = "dev-only-change-me"
    frontend_origin: str = "http://localhost:5173"
    upload_dir: str = "../uploads"
    log_level: str = "INFO"
    access_token_minutes: int = 60
    max_upload_mb: int = 5
    # Optional free job-source keys (leave empty to skip that source)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "gb"
    jooble_api_key: str = ""
    enable_arbeitnow: bool = False  # personal, non-commercial use only per its terms


settings = Settings()
