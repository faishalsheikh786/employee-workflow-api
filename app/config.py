from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "local"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "employee_ops"
    db_user: str = "portaladmin"
    db_password: str = "change-me"
    internal_api_key: str = "change-me"
    cors_origins: str = "http://localhost:5173"
    skip_db_init: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
