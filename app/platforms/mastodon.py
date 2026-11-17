from typing import Optional

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult


class MastodonPlatform(BasePlatform):
    platform_name = "Mastodon"

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=settings.http_timeout)
        self.base_url = settings.mastodon_base_url.strip().rstrip("/")
        self.access_token = settings.mastodon_access_token.strip()

    def missing_credentials(self) -> list[str]:
        missing = []
        if not self.base_url:
            missing.append("MASTODON_BASE_URL")
        if not self.access_token:
            missing.append("MASTODON_ACCESS_TOKEN")
        return missing

    async def _publish(self, message: str, client: httpx.AsyncClient) -> PlatformResult:
        response = await client.post(
            f"{self.base_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {self.access_token}"},
            data={"status": message, "visibility": "public"},
        )
        if response.status_code not in (200, 201):
            return self.failed(self.map_http_error(response.status_code, self._error_detail(response)))

        try:
            data = response.json()
        except ValueError:
            return self.failed("Invalid API response")

        posted_url = data.get("url")
        if not isinstance(posted_url, str) or not posted_url:
            return self.failed("Invalid API response: missing status URL")

        when = self.parse_iso_datetime(data.get("created_at"))
        return self.success(posted_url, public_access=data.get("visibility") == "public", when=when)

    def _error_detail(self, response: httpx.Response) -> Optional[str]:
        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict) and isinstance(data.get("error"), str):
            return data["error"][:200]
        return None
