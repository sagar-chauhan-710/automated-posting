from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.schemas import PlatformResult
from app.services.posting_service import PostingService

client = TestClient(app)

VALID_MESSAGE = "Discover our new business platform today! https://example.com"


def _result(platform: str, status: str, error: Optional[str] = None) -> PlatformResult:
    if status == "success":
        return PlatformResult(
            platform=platform,
            status="success",
            posted_url=f"https://example.com/{platform.lower()}",
            public_access=True,
            date="2026-11-16",
            time="17:30:00",
            error=None,
        )
    return PlatformResult(
        platform=platform,
        status="failed",
        posted_url=None,
        public_access=False,
        date=None,
        time=None,
        error=error or "failed",
    )


@pytest.mark.asyncio
async def test_all_five_platforms_succeed():
    service = PostingService(Settings())
    successes = [
        _result("Telegram", "success"),
        _result("Discord", "success"),
        _result("Bluesky", "success"),
        _result("Mastodon", "success"),
        _result("Slack", "success"),
    ]

    with patch.object(PostingService, "_publish_safely", new_callable=AsyncMock) as mocked:
        mocked.side_effect = successes
        response = await service.post_to_all(VALID_MESSAGE)

    assert response.success is True
    assert len(response.results) == 5
    assert all(item.status == "success" for item in response.results)


@pytest.mark.asyncio
async def test_one_platform_fails_others_succeed():
    service = PostingService(Settings())
    mixed = [
        _result("Telegram", "success"),
        _result("Discord", "failed", "Authentication failed"),
        _result("Bluesky", "success"),
        _result("Mastodon", "success"),
        _result("Slack", "success"),
    ]

    with patch.object(PostingService, "_publish_safely", new_callable=AsyncMock) as mocked:
        mocked.side_effect = mixed
        response = await service.post_to_all(VALID_MESSAGE)

    assert response.success is True
    assert sum(1 for item in response.results if item.status == "failed") == 1


@pytest.mark.asyncio
async def test_multiple_platforms_fail():
    service = PostingService(Settings())
    mixed = [
        _result("Telegram", "failed", "Missing credentials"),
        _result("Discord", "failed", "Authentication failed"),
        _result("Bluesky", "success"),
        _result("Mastodon", "failed", "Rate limit exceeded"),
        _result("Slack", "success"),
    ]

    with patch.object(PostingService, "_publish_safely", new_callable=AsyncMock) as mocked:
        mocked.side_effect = mixed
        response = await service.post_to_all(VALID_MESSAGE)

    assert response.success is True
    assert sum(1 for item in response.results if item.status == "failed") == 3


@pytest.mark.asyncio
async def test_all_platforms_fail():
    service = PostingService(Settings())
    failures = [
        _result("Telegram", "failed", "Missing credentials"),
        _result("Discord", "failed", "Missing credentials"),
        _result("Bluesky", "failed", "Missing credentials"),
        _result("Mastodon", "failed", "Missing credentials"),
        _result("Slack", "failed", "Missing credentials"),
    ]

    with patch.object(PostingService, "_publish_safely", new_callable=AsyncMock) as mocked:
        mocked.side_effect = failures
        response = await service.post_to_all(VALID_MESSAGE)

    assert response.success is False
    assert all(item.status == "failed" for item in response.results)


@pytest.mark.asyncio
async def test_missing_credentials_reported_per_platform():
    settings = Settings(
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_CHANNEL_ID="",
        DISCORD_WEBHOOK_URL="",
        DISCORD_GUILD_ID="",
        BLUESKY_IDENTIFIER="",
        BLUESKY_APP_PASSWORD="",
        MASTODON_BASE_URL="",
        MASTODON_ACCESS_TOKEN="",
        SLACK_WEBHOOK_URL="",
    )
    service = PostingService(settings)
    response = await service.post_to_all(VALID_MESSAGE)

    assert response.success is False
    assert len(response.results) == 5
    for result in response.results:
        assert result.status == "failed"
        assert result.error is not None
        assert "Missing credentials" in result.error


@pytest.mark.asyncio
async def test_unexpected_exception_from_one_integration():
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        TELEGRAM_CHANNEL_ID="@channel",
        DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1/abc",
        DISCORD_GUILD_ID="123",
        BLUESKY_IDENTIFIER="user.bsky.social",
        BLUESKY_APP_PASSWORD="app-pass",
        MASTODON_BASE_URL="https://mastodon.social",
        MASTODON_ACCESS_TOKEN="token",
        SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00/B00/XXX",
    )
    service = PostingService(settings)

    async def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    with patch.object(service.platforms["telegram"], "publish", side_effect=boom):
        with patch.object(
            service.platforms["discord"],
            "publish",
            new=AsyncMock(return_value=_result("Discord", "success")),
        ):
            with patch.object(
                service.platforms["bluesky"],
                "publish",
                new=AsyncMock(return_value=_result("Bluesky", "success")),
            ):
                with patch.object(
                    service.platforms["mastodon"],
                    "publish",
                    new=AsyncMock(return_value=_result("Mastodon", "success")),
                ):
                    with patch.object(
                        service.platforms["slack"],
                        "publish",
                        new=AsyncMock(return_value=_result("Slack", "success")),
                    ):
                        response = await service.post_to_all(VALID_MESSAGE)

    assert response.success is True
    assert response.results[0].status == "failed"
    assert response.results[0].error == "Unexpected error while publishing"
    assert sum(1 for item in response.results if item.status == "success") == 4


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_ui_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"Automated Posting" in response.content


@pytest.mark.asyncio
async def test_selected_platforms_only():
    service = PostingService(Settings())
    selected = [
        _result("Telegram", "success"),
        _result("Discord", "success"),
    ]

    with patch.object(PostingService, "_publish_safely", new_callable=AsyncMock) as mocked:
        mocked.side_effect = selected
        response = await service.post_to_all(
            VALID_MESSAGE,
            platforms=["telegram", "discord"],
        )

    assert response.success is True
    assert len(response.results) == 2
    assert mocked.await_count == 2
    called_names = [call.args[0].platform_name for call in mocked.await_args_list]
    assert called_names == ["Telegram", "Discord"]
