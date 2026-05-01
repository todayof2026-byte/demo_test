"""Typed configuration loader.

Settings come from three sources, in increasing precedence:

1. Built-in profile defaults (``PROFILES`` below).
2. ``.env`` file at the repo root (loaded by pydantic-settings).
3. Real environment variables.

Tests should always go through :func:`get_settings` rather than reading
environment variables directly - that keeps the configuration boundary in
exactly one place (Single Responsibility Principle).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProfileName = Literal["default"]


# Built-in storefront profiles. Adding a new region/site is one entry here.
# The framework targets automationexercise.com - a public, automation-friendly
# e-commerce demo whose markup exposes stable ``data-qa`` attributes purpose-
# built for QA tests.
PROFILES: dict[ProfileName, dict[str, str]] = {
    "default": {
        "base_url": "https://www.automationexercise.com",
        "currency_symbol": "Rs.",
        "currency_code": "INR",
        "decimal_separator": ".",
    },
}


REPO_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    profile: ProfileName = Field(default="default", description="Storefront profile id.")

    site_email: str = Field(
        default="",
        description="Login email. Required for authenticated sessions.",
    )
    site_password: SecretStr = Field(
        default=SecretStr(""),
        description="Password for SITE_EMAIL. Stored as SecretStr so it never appears in repr().",
    )

    headed: bool = Field(default=False, description="Run with a visible browser window.")
    slow_mo: int = Field(default=0, ge=0, description="Slow each Playwright action by N ms.")
    action_timeout_ms: int = Field(default=15_000, ge=1_000)
    navigation_timeout_ms: int = Field(default=30_000, ge=1_000)

    trace_mode: Literal["on", "off", "retain-on-failure", "on-first-retry"] = Field(
        default="retain-on-failure"
    )

    @field_validator("profile", mode="before")
    @classmethod
    def _normalise_profile(cls, value: str) -> str:
        return str(value).strip().lower()

    @property
    def base_url(self) -> str:
        return PROFILES[self.profile]["base_url"]

    @property
    def currency_symbol(self) -> str:
        return PROFILES[self.profile]["currency_symbol"]

    @property
    def currency_code(self) -> str:
        return PROFILES[self.profile]["currency_code"]

    @property
    def decimal_separator(self) -> str:
        return PROFILES[self.profile]["decimal_separator"]

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def auth_dir(self) -> Path:
        path = REPO_ROOT / "auth"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def storage_state_path(self) -> Path:
        return self.auth_dir / "storage_state.json"

    @property
    def reports_dir(self) -> Path:
        path = REPO_ROOT / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def screenshots_dir(self) -> Path:
        path = REPO_ROOT / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data_dir(self) -> Path:
        return REPO_ROOT / "data"

    def has_credentials(self) -> bool:
        """True if both email and password are populated (not stub values)."""
        return bool(self.site_email) and bool(self.site_password.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide singleton Settings instance."""
    return Settings()
