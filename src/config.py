"""Runtime configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/onboarding.db"

    mock_integrations: bool = True
    questionnaire_degrade_days: int = 3
    reminder_days: int = 3

    docusign_webhook_secret: str = "replace-me"
    pandadoc_webhook_secret: str = "replace-me"

    typeform_api_token: str = ""
    calendly_api_token: str = ""
    calendly_event_type_uri: str = ""
    clickup_api_token: str = ""
    clickup_workspace_id: str = ""
    slack_bot_token: str = ""
    google_drive_credentials_path: str = ""
    google_drive_parent_folder_id: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"

    agency_name: str = "Halo Brand Studio"
    agency_domain: str = "halo.studio"
    slack_channel_prefix: str = Field(default="client")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Tests can call this to pick up env changes."""
    get_settings.cache_clear()
