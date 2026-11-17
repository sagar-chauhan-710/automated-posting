import re
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 200
PlatformKey = Literal["telegram", "discord", "bluesky", "mastodon", "slack"]

PLATFORM_KEYS: tuple[PlatformKey, ...] = (
    "telegram",
    "discord",
    "bluesky",
    "mastodon",
    "slack",
)

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
UNSUPPORTED_SCHEME_PATTERN = re.compile(
    r"(?:^|[\s\"'(])(?:javascript|ftp|file):",
    re.IGNORECASE,
)


def _strip_trailing_punctuation(url: str) -> str:
    return url.rstrip(".,;:!?)>]}\"'" )


def extract_urls(message: str) -> list[str]:
    return [_strip_trailing_punctuation(m.group(0)) for m in URL_PATTERN.finditer(message)]


def validate_http_url(url: str) -> None:
    if any(ch.isspace() for ch in url):
        raise ValueError("URL must not contain whitespace")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    if scheme in {"javascript", "ftp", "file"}:
        raise ValueError(f"Unsupported URL scheme: {scheme}")
    if scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a valid hostname")
    if " " in hostname or hostname.startswith(".") or hostname.endswith("."):
        raise ValueError("URL hostname is malformed")
    if "." not in hostname and hostname.lower() != "localhost":
        raise ValueError("URL hostname is malformed")


class PostingRequest(BaseModel):
    message: str
    platforms: Optional[list[PlatformKey]] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if value is None:
            raise ValueError("Message is required")
        if not value.strip():
            raise ValueError("Message cannot be empty or contain only whitespace")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message must be at most {MAX_MESSAGE_LENGTH} characters")
        if UNSUPPORTED_SCHEME_PATTERN.search(value):
            raise ValueError("Message contains an unsupported URL scheme")

        urls = extract_urls(value)
        if len(urls) == 0:
            raise ValueError("Message must contain exactly one HTTP or HTTPS URL")
        if len(urls) > 1:
            raise ValueError("Message must contain exactly one URL")

        validate_http_url(urls[0])
        return value

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value: Optional[list[PlatformKey]]) -> Optional[list[PlatformKey]]:
        if value is None:
            return None
        if not value:
            raise ValueError("Select at least one platform")

        # keep order, drop duplicates
        unique: list[PlatformKey] = []
        for item in value:
            if item not in unique:
                unique.append(item)
        return unique


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[str] = None
    time: Optional[str] = None
    error: Optional[str] = None


class PostingResponse(BaseModel):
    success: bool
    results: list[PlatformResult]
