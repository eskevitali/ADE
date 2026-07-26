"""Centralized configuration for ADE v4."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    XAI = "xai"


class ADEConfig(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    root_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    projects_dir: Path | None = None
    knowledge_dir: Path | None = None
    reviews_dir: Path | None = None
    governance_dir: Path | None = None
    docker_dir: Path | None = None
    scripts_dir: Path | None = None

    # LLM
    openrouter_api_key: str = ""
    xai_api_key: str = ""
    default_provider: LLMProvider = LLMProvider.OPENROUTER
    default_temperature: float = 0.2
    llm_cache_enabled: bool = True

    # Docker / ADI isolation
    docker_network_prefix: str = "ade-adi"
    docker_socket: str = "unix:///var/run/docker.sock"
    docker_default_image: str = "python:3.12-slim"
    workspace_proxy_network: str = "ade-v4_default"

    # Services
    qdrant_url: str = "http://localhost:6333"
    postgres_url: str = "postgresql://ade:ade@localhost:5432/ade"
    redis_url: str = "redis://localhost:6379/0"

    # Recovery loop (Tester-driven auto-fix on deploy/rebuild failures)
    max_recovery_attempts: int = 3

    # App
    app_env: str = "development"
    log_level: str = "info"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    domain: str = "ade.kider.at"

    # Auth (session-based)
    session_secret: str = "ade-v4-change-this-secret-in-production"
    admin_username: str = "eskevitali@gmail.com"
    admin_password: str = "777025!Jestex"

    def model_post_init(self, __context: object) -> None:
        defaults = {
            "projects_dir": self.root_dir / "projects",
            "knowledge_dir": self.root_dir / "knowledge",
            "reviews_dir": self.root_dir / "reviews",
            "governance_dir": self.root_dir / "governance",
            "docker_dir": self.root_dir / "docker",
            "scripts_dir": self.root_dir / "scripts",
        }
        for key, value in defaults.items():
            if getattr(self, key) is None:
                object.__setattr__(self, key, value)

    def has_openrouter(self) -> bool:
        return bool(self.openrouter_api_key)

    def has_xai(self) -> bool:
        return bool(self.xai_api_key)

    def ensure_dirs(self) -> None:
        """Create project directories if they do not exist."""
        for path in (
            self.projects_dir,
            self.knowledge_dir,
            self.reviews_dir,
            self.governance_dir,
            self.docker_dir,
            self.scripts_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_config() -> ADEConfig:
    """Return cached application configuration."""
    return ADEConfig()
