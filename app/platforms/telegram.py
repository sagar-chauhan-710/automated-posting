from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult


class TelegramPlatform(BasePlatform):
    platform_name = "Telegram"

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=settings.http_timeout)
        self.bot_token = settings.telegram_bot_token.strip()
        self.channel_id = settings.telegram_channel_id.strip()
        username = settings.telegram_public_username.strip()
        if not username and self.channel_id.startswith("@"):
            username = self.channel_id
        self.public_username = username.lstrip("@").strip()

    def missing_credentials(self) -> list[str]:
        missing = []
        if not self.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.channel_id:
            missing.append("TELEGRAM_CHANNEL_ID")
        return missing

    async def _publish(self, message: str, client: httpx.AsyncClient) -> PlatformResult:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = await client.post(
            url,
            json={"chat_id": self.channel_id, "text": message},
        )

        try:
            data = response.json()
        except ValueError:
            return self.failed(self.map_http_error(response.status_code, "Invalid API response"))

        if response.status_code != 200 or not data.get("ok"):
            detail = None
            if isinstance(data, dict) and data.get("description"):
                detail = str(data["description"])[:200]
            return self.failed(self.map_http_error(response.status_code, detail))

        result = data.get("result") or {}
        message_id = result.get("message_id")
        if message_id is None:
            return self.failed("Invalid API response: missing message_id")

        posted_url = None
        public_access = False
        if self.public_username:
            posted_url = f"https://t.me/{self.public_username}/{message_id}"
            public_access = True

        when = None
        if isinstance(result.get("date"), int):
            when = datetime.fromtimestamp(result["date"], tz=timezone.utc)

        return self.success(posted_url, public_access=public_access, when=when)
