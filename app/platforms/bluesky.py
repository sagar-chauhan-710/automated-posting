from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional, Union

import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

URL_FACET_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class BlueskyPlatform(BasePlatform):
    platform_name = "Bluesky"

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout=settings.http_timeout)
        self.identifier = settings.bluesky_identifier.strip()
        self.app_password = settings.bluesky_app_password.strip()
        self.pds_url = settings.bluesky_pds_url.rstrip("/")

    def missing_credentials(self) -> list[str]:
        missing = []
        if not self.identifier:
            missing.append("BLUESKY_IDENTIFIER")
        if not self.app_password:
            missing.append("BLUESKY_APP_PASSWORD")
        return missing

    async def _publish(self, message: str, client: httpx.AsyncClient) -> PlatformResult:
        session = await self._create_session(client)
        if isinstance(session, PlatformResult):
            return session

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": created_at,
        }
        facets = self._link_facets(message)
        if facets:
            record["facets"] = facets

        response = await client.post(
            f"{self.pds_url}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": record,
            },
        )
        if response.status_code != 200:
            return self.failed(self.map_http_error(response.status_code, self._error_message(response)))

        try:
            data = response.json()
        except ValueError:
            return self.failed("Invalid API response")

        uri = data.get("uri")
        if not isinstance(uri, str) or not uri:
            return self.failed("Invalid API response: missing AT URI")

        rkey = uri.rstrip("/").split("/")[-1]
        if not rkey:
            return self.failed("Invalid API response: could not parse record key")

        handle = session.get("handle") or self.identifier
        posted_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
        return self.success(posted_url, public_access=True, when=self.parse_iso_datetime(created_at))

    async def _create_session(
        self, client: httpx.AsyncClient
    ) -> Union[dict[str, Any], PlatformResult]:
        response = await client.post(
            f"{self.pds_url}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.identifier, "password": self.app_password},
        )
        if response.status_code != 200:
            return self.failed(self.map_http_error(response.status_code, self._error_message(response)))

        try:
            data = response.json()
        except ValueError:
            return self.failed("Invalid API response during authentication")

        if not data.get("accessJwt") or not data.get("did"):
            return self.failed("Invalid API response: missing session credentials")
        return data

    def _link_facets(self, text: str) -> list[dict[str, Any]]:
        facets = []
        text_bytes = text.encode("utf-8")
        for match in URL_FACET_PATTERN.finditer(text):
            url = match.group(0).rstrip(".,;:!?)>]}\"'" )
            start = len(text[: match.start()].encode("utf-8"))
            end = start + len(url.encode("utf-8"))
            if end > len(text_bytes):
                continue
            facets.append(
                {
                    "index": {"byteStart": start, "byteEnd": end},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
                }
            )
        return facets

    def _error_message(self, response: httpx.Response) -> Optional[str]:
        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error")
            if isinstance(msg, str):
                return msg[:200]
        return None
