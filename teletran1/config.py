"""Configuration management for Teletran1."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Teletran1 configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Notion Integration
    notion_api_key: str
    notion_database_id: str

    # Anthropic Claude
    anthropic_api_key: str
    model_name: str = "claude-sonnet-4-5-20250929"

    # Personality settings (could be extended later)
    personality_type: str = "ENTP"


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
