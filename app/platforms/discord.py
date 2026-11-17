from typing import Optional

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult


class DiscordPlatform(BasePlatform):
    platform_name = "Discord"

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=settings.http_timeout)
        self.webhook_url = settings.discord_webhook_url.strip()
        self.guild_id = settings.discord_guild_id.strip()
        self.channel_is_public = settings.discord_channel_is_public

    def missing_credentials(self) -> list[str]:
        missing = []
        if not self.webhook_url:
            missing.append("DISCORD_WEBHOOK_URL")
        if not self.guild_id:
            missing.append("DISCORD_GUILD_ID")
        return missing

    async def _publish(self, message: str, client: httpx.AsyncClient) -> PlatformResult:
        # wait=true so Discord returns the message object
        sep = "&" if "?" in self.webhook_url else "?"
        url = f"{self.webhook_url}{sep}wait=true"

        response = await client.post(url, json={"content": message})
        if response.status_code not in (200, 201):
            return self.failed(self.map_http_error(response.status_code, self._error_detail(response)))

        try:
            data = response.json()
        except ValueError:
            return self.failed("Invalid API response")

        message_id = data.get("id")
        channel_id = data.get("channel_id")
        if not message_id or not channel_id:
            return self.failed("Invalid API response: missing message or channel id")

        posted_url = f"https://discord.com/channels/{self.guild_id}/{channel_id}/{message_id}"
        when = self.parse_iso_datetime(data.get("timestamp"))
        return self.success(posted_url, public_access=self.channel_is_public, when=when)

    def _error_detail(self, response: httpx.Response) -> Optional[str]:
        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict) and isinstance(data.get("message"), str):
            return data["message"][:200]
        return None
