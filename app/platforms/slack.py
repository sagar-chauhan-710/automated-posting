from typing import Optional

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult


class SlackPlatform(BasePlatform):
    platform_name = "Slack"

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=settings.http_timeout)
        self.webhook_url = settings.slack_webhook_url.strip()
        self.channel_url = settings.slack_channel_url.strip()
        self.channel_is_public = settings.slack_channel_is_public

    def missing_credentials(self) -> list[str]:
        return [] if self.webhook_url else ["SLACK_WEBHOOK_URL"]

    async def _publish(self, message: str, client: httpx.AsyncClient) -> PlatformResult:
        response = await client.post(
            self.webhook_url,
            json={"text": message},
            headers={"Content-Type": "application/json"},
        )
        body = (response.text or "").strip()

        if response.status_code not in (200, 201) or body != "ok":
            return self.failed(self._map_slack_error(response.status_code, body))

        # webhook response is just "ok", so channel link is optional
        posted_url: Optional[str] = self.channel_url or None
        public_access = bool(self.channel_url) and self.channel_is_public
        return self.success(posted_url, public_access=public_access)

    def _map_slack_error(self, status_code: int, body: str) -> str:
        known = {
            "invalid_payload": "Bad request: invalid payload",
            "invalid_token": "Authentication failed",
            "no_service": "Resource not found: webhook disabled or invalid",
            "channel_not_found": "Resource not found: channel not found",
            "channel_is_archived": "Bad request: channel is archived",
            "action_prohibited": "Access forbidden",
            "no_text": "Bad request: missing text",
            "posting_to_general_channel_denied": "Access forbidden: posting to #general denied",
        }
        if body in known:
            return known[body]
        if body and body != "ok":
            return self.map_http_error(status_code, body[:160])
        return self.map_http_error(status_code)
