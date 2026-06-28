"""
config.py — Centralised configuration loaded from environment variables.

All settings are validated by pydantic-settings; missing required keys
raise a clear error at startup rather than at call-time.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Required ──────────────────────────────────────────────────────────────
    github_token: str = Field(..., description="GitHub Personal Access Token")
    telegram_bot_token: str = Field(..., description="Telegram Bot Token from @BotFather")
    telegram_chat_id: str = Field(..., description="Telegram channel/group chat ID")

    # ── Optional ──────────────────────────────────────────────────────────────
    dry_run: bool = Field(False, description="Generate content but skip Telegram posting")
    min_stars: int = Field(300, description="Minimum star count for a repo to qualify")

    # ── Scoring weights ───────────────────────────────────────────────────────
    weight_stars: float = Field(0.25)
    weight_recent_activity: float = Field(0.20)
    weight_growth_potential: float = Field(0.10)
    weight_readme_quality: float = Field(0.10)
    weight_contributors: float = Field(0.10)
    weight_issue_activity: float = Field(0.05)
    weight_documentation: float = Field(0.10)
    weight_popularity: float = Field(0.05)
    weight_community: float = Field(0.05)

    # ── Paths ─────────────────────────────────────────────────────────────────
    data_dir: str = Field("data", description="Directory for JSON history/cache files")
    assets_dir: str = Field("assets", description="Directory for generated thumbnails")
    reports_dir: str = Field("reports", description="Directory for HTML reports")
    logs_dir: str = Field("logs", description="Directory for log files")

    # ── GitHub search config ──────────────────────────────────────────────────
    max_repos_per_source: int = Field(50, description="Max repos fetched per discovery source")
    request_timeout: int = Field(30, description="HTTP request timeout in seconds")

    @field_validator("weight_stars", "weight_recent_activity", "weight_growth_potential",
                     "weight_readme_quality", "weight_contributors", "weight_issue_activity",
                     "weight_documentation", "weight_popularity", "weight_community")
    @classmethod
    def _positive_weight(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("Weight must be between 0 and 1")
        return v

    @property
    def weights(self) -> dict[str, float]:
        return {
            "stars": self.weight_stars,
            "recent_activity": self.weight_recent_activity,
            "growth_potential": self.weight_growth_potential,
            "readme_quality": self.weight_readme_quality,
            "contributors": self.weight_contributors,
            "issue_activity": self.weight_issue_activity,
            "documentation": self.weight_documentation,
            "popularity": self.weight_popularity,
            "community": self.weight_community,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
