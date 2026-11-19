from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables or the .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "CHANGE_ME"  # must be overridden in .env
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = "sqlite:///./crm.db"

    # Frontend origins allowed to call the API, comma separated.
    # "*" is not allowed here: together with allow_credentials=True the
    # browser rejects such a response (CORS specification).
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Public demo: shows the demo logins on the sign-in screen and allows the
    # page to be embedded in an <iframe> on the portfolio site.
    demo_mode: bool = False
    # In demo mode the database is wiped and re-seeded on startup and then
    # every N hours, so visitors always find a working demo.
    demo_reset_hours: float = 6
    # Origins allowed to embed the app (Content-Security-Policy frame-ancestors).
    frame_ancestors: str = "'self'"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
