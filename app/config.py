from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # telegram
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_id: str = Field(default="", alias="TELEGRAM_CHANNEL_ID")
    telegram_public_username: str = Field(default="", alias="TELEGRAM_PUBLIC_USERNAME")

    # discord
    discord_webhook_url: str = Field(default="", alias="DISCORD_WEBHOOK_URL")
    discord_guild_id: str = Field(default="", alias="DISCORD_GUILD_ID")
    discord_public_channel: str = Field(default="false", alias="DISCORD_PUBLIC_CHANNEL")

    # bluesky
    bluesky_identifier: str = Field(default="", alias="BLUESKY_IDENTIFIER")
    bluesky_app_password: str = Field(default="", alias="BLUESKY_APP_PASSWORD")
    bluesky_pds_url: str = Field(default="https://bsky.social", alias="BLUESKY_PDS_URL")

    # mastodon
    mastodon_base_url: str = Field(default="", alias="MASTODON_BASE_URL")
    mastodon_access_token: str = Field(default="", alias="MASTODON_ACCESS_TOKEN")

    # slack
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    slack_channel_url: str = Field(default="", alias="SLACK_CHANNEL_URL")
    slack_public_channel: str = Field(default="false", alias="SLACK_PUBLIC_CHANNEL")

    http_timeout: float = Field(default=30.0, alias="HTTP_TIMEOUT")

    @property
    def discord_channel_is_public(self) -> bool:
        return self.discord_public_channel.strip().lower() in {"1", "true", "yes", "on"}

    @property
    def slack_channel_is_public(self) -> bool:
        return self.slack_public_channel.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
