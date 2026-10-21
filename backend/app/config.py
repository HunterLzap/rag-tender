from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TENDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "投标响应工作台"
    api_prefix: str = "/api/v2"
    data_dir: Path = Path("../data")
    database_url: str | None = None
    worker_poll_seconds: float = 1.0
    job_lease_seconds: int = 120
    max_upload_bytes: int = 100 * 1024 * 1024
    max_pdf_pages: int = 500
    max_zip_entries: int = 10_000
    max_zip_uncompressed_bytes: int = 500 * 1024 * 1024
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str | None = Field(default=None, repr=False)
    libreoffice_path: str | None = None
    render_scale: float = 2.0
    model_timeout_seconds: int = 180
    auto_create_schema: bool = True

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.resolve()

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{self.resolved_data_dir / 'workbench.db'}"

    @property
    def uploads_dir(self) -> Path:
        return self.resolved_data_dir / "uploads"

    @property
    def rendered_dir(self) -> Path:
        return self.resolved_data_dir / "rendered"

    @property
    def exports_dir(self) -> Path:
        return self.resolved_data_dir / "exports"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def ensure_dirs(self) -> None:
        for path in (
            self.resolved_data_dir,
            self.uploads_dir,
            self.rendered_dir,
            self.exports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
