import asyncio
import logging
from typing import Optional

import httpx

from app.config import Settings, get_settings
from app.platforms.base import BasePlatform
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.slack import SlackPlatform
from app.platforms.telegram import TelegramPlatform
from app.schemas import PLATFORM_KEYS, PlatformKey, PlatformResult, PostingResponse

logger = logging.getLogger(__name__)


class PostingService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.platforms: dict[str, BasePlatform] = {
            "telegram": TelegramPlatform(self.settings),
            "discord": DiscordPlatform(self.settings),
            "bluesky": BlueskyPlatform(self.settings),
            "mastodon": MastodonPlatform(self.settings),
            "slack": SlackPlatform(self.settings),
        }

    async def post_to_all(
        self,
        message: str,
        platforms: Optional[list[PlatformKey]] = None,
    ) -> PostingResponse:
        keys = platforms or list(PLATFORM_KEYS)
        selected = [self.platforms[key] for key in keys]

        async with httpx.AsyncClient(timeout=self.settings.http_timeout) as client:
            results = await asyncio.gather(
                *[self._publish_safely(p, message, client) for p in selected]
            )

        ok = any(r.status == "success" for r in results)
        return PostingResponse(success=ok, results=list(results))

    async def _publish_safely(
        self,
        platform: BasePlatform,
        message: str,
        client: httpx.AsyncClient,
    ) -> PlatformResult:
        try:
            return await platform.publish(message, client=client)
        except Exception:
            logger.exception("%s failed unexpectedly", platform.platform_name)
            return platform.failed("Unexpected error while publishing")
