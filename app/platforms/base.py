from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.schemas import PlatformResult


class BasePlatform(ABC):
    platform_name: str = "Unknown"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @abstractmethod
    def missing_credentials(self) -> list[str]:
        pass

    @abstractmethod
    async def _publish(self, message: str, client: httpx.AsyncClient) -> PlatformResult:
        pass

    async def publish(self, message: str, client: Optional[httpx.AsyncClient] = None) -> PlatformResult:
        missing = self.missing_credentials()
        if missing:
            return self.failed(f"Missing credentials: {', '.join(missing)}")

        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        try:
            assert client is not None
            return await self._publish(message, client)
        except httpx.TimeoutException:
            return self.failed("Network timeout while contacting the platform API")
        except httpx.NetworkError:
            return self.failed("Connection failure while contacting the platform API")
        except Exception:
            return self.failed("Unexpected error while publishing")
        finally:
            if owns_client and client is not None:
                await client.aclose()

    def success(
        self,
        posted_url: Optional[str],
        *,
        public_access: bool,
        when: Optional[datetime] = None,
    ) -> PlatformResult:
        ts = when or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        return PlatformResult(
            platform=self.platform_name,
            status="success",
            posted_url=posted_url,
            public_access=public_access,
            date=ts.strftime("%Y-%m-%d"),
            time=ts.strftime("%H:%M:%S"),
            error=None,
        )

    def failed(self, error: str) -> PlatformResult:
        return PlatformResult(
            platform=self.platform_name,
            status="failed",
            posted_url=None,
            public_access=False,
            date=None,
            time=None,
            error=error,
        )

    def map_http_error(self, status_code: int, detail: Optional[str] = None) -> str:
        messages = {
            400: "Bad request",
            401: "Authentication failed",
            403: "Access forbidden",
            404: "Resource not found",
            429: "Rate limit exceeded",
            500: "Platform server error",
        }
        base = messages.get(status_code, f"HTTP {status_code} error")
        return f"{base}: {detail}" if detail else base

    @staticmethod
    def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
