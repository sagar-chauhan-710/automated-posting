import json

import httpx
import pytest
import respx

from app.config import Settings
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.slack import SlackPlatform
from app.platforms.telegram import TelegramPlatform

MESSAGE = "Discover our new business platform today! https://example.com"


def _settings(**overrides) -> Settings:
    defaults = {
        "TELEGRAM_BOT_TOKEN": "tg-token",
        "TELEGRAM_CHANNEL_ID": "@newsroom",
        "TELEGRAM_PUBLIC_USERNAME": "newsroom",
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/111/abc",
        "DISCORD_GUILD_ID": "222",
        "DISCORD_PUBLIC_CHANNEL": "true",
        "BLUESKY_IDENTIFIER": "demo.bsky.social",
        "BLUESKY_APP_PASSWORD": "app-password",
        "BLUESKY_PDS_URL": "https://bsky.social",
        "MASTODON_BASE_URL": "https://mastodon.social",
        "MASTODON_ACCESS_TOKEN": "mastodon-token",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T00/B00/XXX",
        "SLACK_CHANNEL_URL": "https://example.slack.com/archives/C00",
        "SLACK_PUBLIC_CHANNEL": "false",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
@respx.mock
async def test_telegram_success_builds_permalink():
    route = respx.post("https://api.telegram.org/bottg-token/sendMessage").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 42,
                    "date": 1731778200,
                    "chat": {"id": -1001, "username": "newsroom"},
                },
            },
        )
    )

    platform = TelegramPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "success"
    assert result.posted_url == "https://t.me/newsroom/42"
    assert result.public_access is True
    assert route.called
    request = route.calls.last.request
    body = json.loads(request.content.decode())
    assert body == {"chat_id": "@newsroom", "text": MESSAGE}


@pytest.mark.asyncio
@respx.mock
async def test_telegram_auth_error():
    respx.post("https://api.telegram.org/bottg-token/sendMessage").mock(
        return_value=httpx.Response(
            401,
            json={"ok": False, "description": "Unauthorized"},
        )
    )

    platform = TelegramPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "failed"
    assert "Authentication failed" in (result.error or "")


@pytest.mark.asyncio
@respx.mock
async def test_discord_success_builds_permalink_and_respects_public_flag():
    route = respx.post(
        url__regex=r"https://discord\.com/api/webhooks/111/abc\?wait=true"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "999",
                "channel_id": "333",
                "timestamp": "2026-11-16T17:30:00.000000+00:00",
                "content": MESSAGE,
            },
        )
    )

    platform = DiscordPlatform(_settings(DISCORD_PUBLIC_CHANNEL="true"))
    result = await platform.publish(MESSAGE)

    assert result.status == "success"
    assert result.posted_url == "https://discord.com/channels/222/333/999"
    assert result.public_access is True
    assert route.called
    request = route.calls.last.request
    assert json.loads(request.content.decode()) == {"content": MESSAGE}


@pytest.mark.asyncio
@respx.mock
async def test_discord_private_channel_sets_public_access_false():
    respx.post(url__regex=r".*wait=true").mock(
        return_value=httpx.Response(
            200,
            json={"id": "999", "channel_id": "333", "timestamp": "2026-11-16T17:30:00Z"},
        )
    )

    platform = DiscordPlatform(_settings(DISCORD_PUBLIC_CHANNEL="false"))
    result = await platform.publish(MESSAGE)

    assert result.status == "success"
    assert result.public_access is False


@pytest.mark.asyncio
@respx.mock
async def test_discord_invalid_webhook():
    respx.post(url__regex=r".*wait=true").mock(
        return_value=httpx.Response(404, json={"message": "Unknown Webhook"})
    )

    platform = DiscordPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "failed"
    assert "Resource not found" in (result.error or "")


@pytest.mark.asyncio
@respx.mock
async def test_bluesky_success_session_and_create_record():
    session_route = respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").mock(
        return_value=httpx.Response(
            200,
            json={
                "accessJwt": "jwt-token",
                "refreshJwt": "refresh",
                "did": "did:plc:abcdef",
                "handle": "demo.bsky.social",
            },
        )
    )
    create_route = respx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").mock(
        return_value=httpx.Response(
            200,
            json={
                "uri": "at://did:plc:abcdef/app.bsky.feed.post/3kxyz",
                "cid": "bafytest",
            },
        )
    )

    platform = BlueskyPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "success"
    assert result.posted_url == "https://bsky.app/profile/demo.bsky.social/post/3kxyz"
    assert result.public_access is True
    assert session_route.called
    assert create_route.called

    session_body = json.loads(session_route.calls.last.request.content.decode())
    assert session_body == {
        "identifier": "demo.bsky.social",
        "password": "app-password",
    }

    create_request = create_route.calls.last.request
    assert create_request.headers["Authorization"] == "Bearer jwt-token"
    create_body = json.loads(create_request.content.decode())
    assert create_body["repo"] == "did:plc:abcdef"
    assert create_body["collection"] == "app.bsky.feed.post"
    assert create_body["record"]["text"] == MESSAGE
    assert create_body["record"]["$type"] == "app.bsky.feed.post"


@pytest.mark.asyncio
@respx.mock
async def test_bluesky_invalid_credentials():
    respx.post("https://bsky.social/xrpc/com.atproto.server.createSession").mock(
        return_value=httpx.Response(401, json={"error": "AuthenticationRequired", "message": "Invalid identifier or password"})
    )

    platform = BlueskyPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "failed"
    assert "Authentication failed" in (result.error or "")


@pytest.mark.asyncio
@respx.mock
async def test_mastodon_success_uses_status_url():
    route = respx.post("https://mastodon.social/api/v1/statuses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "109",
                "url": "https://mastodon.social/@demo/109",
                "visibility": "public",
                "created_at": "2026-11-16T17:30:00.000Z",
            },
        )
    )

    platform = MastodonPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "success"
    assert result.posted_url == "https://mastodon.social/@demo/109"
    assert result.public_access is True
    assert route.called

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer mastodon-token"
    assert b"status=" in request.content
    assert b"visibility=public" in request.content


@pytest.mark.asyncio
@respx.mock
async def test_mastodon_rate_limit():
    respx.post("https://mastodon.social/api/v1/statuses").mock(
        return_value=httpx.Response(429, json={"error": "Too many requests"})
    )

    platform = MastodonPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "failed"
    assert "Rate limit exceeded" in (result.error or "")


@pytest.mark.asyncio
@respx.mock
async def test_slack_success_posts_text_payload():
    route = respx.post("https://hooks.slack.com/services/T00/B00/XXX").mock(
        return_value=httpx.Response(200, text="ok")
    )

    platform = SlackPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "success"
    assert result.posted_url == "https://example.slack.com/archives/C00"
    assert result.public_access is False
    assert route.called

    request = route.calls.last.request
    assert json.loads(request.content.decode()) == {"text": MESSAGE}


@pytest.mark.asyncio
@respx.mock
async def test_slack_invalid_webhook():
    respx.post("https://hooks.slack.com/services/T00/B00/XXX").mock(
        return_value=httpx.Response(404, text="no_service")
    )

    platform = SlackPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "failed"
    assert "Resource not found" in (result.error or "")


@pytest.mark.asyncio
@respx.mock
async def test_slack_auth_failure():
    respx.post("https://hooks.slack.com/services/T00/B00/XXX").mock(
        return_value=httpx.Response(403, text="invalid_token")
    )

    platform = SlackPlatform(_settings())
    result = await platform.publish(MESSAGE)

    assert result.status == "failed"
    assert "Authentication failed" in (result.error or "")


@pytest.mark.asyncio
async def test_missing_credentials_do_not_call_network():
    platform = TelegramPlatform(
        Settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="")
    )
    result = await platform.publish(MESSAGE)
    assert result.status == "failed"
    assert "Missing credentials" in (result.error or "")
