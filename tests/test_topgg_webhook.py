import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import make_mocked_request

from bot import storage
from bot.settings import VOTE_STARTER_REWARD
from bot.topgg_webhook import (
    TopggWebhookConfig,
    TopggWebhookServer,
    _extract_user_id,
    _is_authorized,
    _is_request_ip_allowed,
    _normalize_route_path,
)


def test_normalize_route_path_prefixes_slash() -> None:
    assert _normalize_route_path("topgg/vote") == "/topgg/vote"


def test_extract_user_id_accepts_numeric_string() -> None:
    assert _extract_user_id({"user": "123"}) == 123


def test_extract_user_id_rejects_non_numeric_value() -> None:
    assert _extract_user_id({"user": "abc"}) is None


def test_is_authorized_compares_header_to_secret() -> None:
    assert _is_authorized("secret", "secret")
    assert not _is_authorized("nope", "secret")


def test_is_request_ip_allowed_allows_when_no_allowlist() -> None:
    assert _is_request_ip_allowed("203.0.113.5", ())

def test_is_request_ip_allowed_rejects_invalid_or_missing_remote() -> None:
    allowlist = ("203.0.113.0/24",)
    server = TopggWebhookServer(
        TopggWebhookConfig(
            secret="secret",
            host="127.0.0.1",
            port=8080,
            path="/bot/topgg-vote-webhook",
            allowed_ip_networks=allowlist,
        )
    )
    assert not _is_request_ip_allowed(None, server._allowed_networks)
    assert not _is_request_ip_allowed("not-an-ip", server._allowed_networks)


def test_is_request_ip_allowed_checks_cidr_membership() -> None:
    allowlist = ("203.0.113.0/24",)
    server = TopggWebhookServer(
        TopggWebhookConfig(
            secret="secret",
            host="127.0.0.1",
            port=8080,
            path="/bot/topgg-vote-webhook",
            allowed_ip_networks=allowlist,
        )
    )
    assert _is_request_ip_allowed("203.0.113.25", server._allowed_networks)
    assert not _is_request_ip_allowed("198.51.100.25", server._allowed_networks)


@pytest.fixture
def webhook_server() -> TopggWebhookServer:
    tmp_dir = tempfile.TemporaryDirectory()
    original_db_path = storage.DB_PATH
    storage.DB_PATH = Path(tmp_dir.name) / "test.db"
    storage.init_db()
    server = TopggWebhookServer(
        TopggWebhookConfig(
            secret="secret",
            host="127.0.0.1",
            port=8080,
            path="/bot/topgg-vote-webhook",
            expected_bot_id="",
        )
    )
    try:
        yield server
    finally:
        storage.DB_PATH = original_db_path
        tmp_dir.cleanup()


async def test_rejects_request_with_invalid_secret(webhook_server: TopggWebhookServer) -> None:
    request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "wrong"},
    )
    request.json = AsyncMock(return_value={"user": "123"})

    response = await webhook_server._handle_vote(request)

    assert response.status == 401


async def test_claims_vote_reward_on_valid_payload(webhook_server: TopggWebhookServer) -> None:
    request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "secret", "Content-Type": "application/json"},
    )
    request.json = AsyncMock(return_value={"user": "123", "type": "upvote"})

    response = await webhook_server._handle_vote(request)

    assert response.status == 200
    assert storage.get_player_starter(0, 123) == VOTE_STARTER_REWARD
    assert storage.get_player_votes(0, 123) == 1


async def test_duplicate_vote_claims_reward_each_time(webhook_server: TopggWebhookServer) -> None:
    first_request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "secret", "Content-Type": "application/json"},
    )
    first_request.json = AsyncMock(return_value={"user": "456", "type": "upvote"})

    second_request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "secret", "Content-Type": "application/json"},
    )
    second_request.json = AsyncMock(return_value={"user": "456", "type": "upvote"})

    first_response = await webhook_server._handle_vote(first_request)

    second_response = await webhook_server._handle_vote(second_request)

    assert first_response.status == 200
    assert second_response.status == 200
    assert storage.get_player_starter(0, 456) == VOTE_STARTER_REWARD * 2
    assert storage.get_player_votes(0, 456) == 2


async def test_rejects_non_json_content_type_when_enforced(webhook_server: TopggWebhookServer) -> None:
    request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "secret", "Content-Type": "text/plain"},
    )
    request.json = AsyncMock(return_value={"user": "123", "type": "upvote"})

    response = await webhook_server._handle_vote(request)

    assert response.status == 415


async def test_rejects_payload_too_large_from_content_length(webhook_server: TopggWebhookServer) -> None:
    request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={
            "Authorization": "secret",
            "Content-Type": "application/json",
            "Content-Length": "999999",
        },
    )
    request.json = AsyncMock(return_value={"user": "123", "type": "upvote"})

    response = await webhook_server._handle_vote(request)

    assert response.status == 413


async def test_acknowledges_test_type_without_claiming_reward(webhook_server: TopggWebhookServer) -> None:
    request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "secret", "Content-Type": "application/json"},
    )
    request.json = AsyncMock(return_value={"user": "123", "type": "test"})

    response = await webhook_server._handle_vote(request)

    assert response.status == 200
    assert storage.get_player_starter(0, 123) == 0
    assert storage.get_player_votes(0, 123) == 0


async def test_rejects_unknown_vote_type(webhook_server: TopggWebhookServer) -> None:
    request = make_mocked_request(
        "POST",
        "/bot/topgg-vote-webhook",
        headers={"Authorization": "secret", "Content-Type": "application/json"},
    )
    request.json = AsyncMock(return_value={"user": "123", "type": "mystery"})

    response = await webhook_server._handle_vote(request)

    assert response.status == 400
    assert storage.get_player_starter(0, 123) == 0
    assert storage.get_player_votes(0, 123) == 0
