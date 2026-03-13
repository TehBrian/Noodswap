import hashlib
import hmac as hmac_module
import json as json_module
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
    _is_request_ip_allowed,
    _normalize_route_path,
    _verify_signature,
)

_SECRET = "whs_testsecret"
_TIMESTAMP = "1700000000"


def _make_sig(secret: str, raw_body: bytes, timestamp: str = _TIMESTAMP) -> str:
    """Build an x-topgg-signature header value matching the v2 HMAC scheme."""
    message = f"{timestamp}.".encode() + raw_body
    sig = hmac_module.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _vote_body(user_platform_id: str, bot_platform_id: str = "BOT123") -> bytes:
    return json_module.dumps(
        {
            "type": "vote.create",
            "data": {
                "id": "1",
                "weight": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": "2026-01-01T12:00:00Z",
                "project": {
                    "id": "proj1",
                    "type": "bot",
                    "platform": "discord",
                    "platform_id": bot_platform_id,
                },
                "user": {
                    "id": "topgg_id",
                    "platform_id": user_platform_id,
                    "name": "testuser",
                    "avatar_url": "",
                },
            },
        }
    ).encode()


def _test_body(user_platform_id: str, bot_platform_id: str = "BOT123") -> bytes:
    return json_module.dumps(
        {
            "type": "webhook.test",
            "data": {
                "project": {
                    "id": "proj1",
                    "type": "bot",
                    "platform": "discord",
                    "platform_id": bot_platform_id,
                },
                "user": {
                    "id": "topgg_id",
                    "platform_id": user_platform_id,
                    "name": "testuser",
                    "avatar_url": "",
                },
            },
        }
    ).encode()


def _mocked_post(
    path: str,
    raw_body: bytes,
    extra_headers: dict | None = None,
    secret: str = _SECRET,
    timestamp: str = _TIMESTAMP,
    content_type: str = "application/json",
) -> object:
    sig = _make_sig(secret, raw_body, timestamp)
    headers = {
        "Content-Type": content_type,
        "x-topgg-signature": sig,
    }
    if extra_headers:
        headers.update(extra_headers)
    request = make_mocked_request("POST", path, headers=headers)
    request.read = AsyncMock(return_value=raw_body)
    return request


def test_normalize_route_path_prefixes_slash() -> None:
    assert _normalize_route_path("noodswap/topgg-vote-webhook") == "/noodswap/topgg-vote-webhook"


def test_extract_user_id_reads_platform_id_from_data_user() -> None:
    payload = {"type": "vote.create", "data": {"user": {"platform_id": "123"}}}
    assert _extract_user_id(payload) == 123


def test_extract_user_id_rejects_non_numeric_platform_id() -> None:
    payload = {"type": "vote.create", "data": {"user": {"platform_id": "abc"}}}
    assert _extract_user_id(payload) is None


def test_extract_user_id_returns_none_when_data_missing() -> None:
    assert _extract_user_id({"type": "vote.create"}) is None


def test_verify_signature_accepts_correct_hmac() -> None:
    body = b'{"type":"vote.create"}'
    header = _make_sig(_SECRET, body)
    assert _verify_signature(body, header, _SECRET)


def test_verify_signature_rejects_wrong_secret() -> None:
    body = b'{"type":"vote.create"}'
    header = _make_sig(_SECRET, body)
    assert not _verify_signature(body, header, "wrong_secret")


def test_verify_signature_rejects_missing_header() -> None:
    body = b'{"type":"vote.create"}'
    assert not _verify_signature(body, None, _SECRET)


def test_verify_signature_rejects_malformed_header() -> None:
    body = b'{"type":"vote.create"}'
    assert not _verify_signature(body, "notaheader", _SECRET)


def test_is_request_ip_allowed_allows_when_no_allowlist() -> None:
    assert _is_request_ip_allowed("203.0.113.5", ())


def test_is_request_ip_allowed_rejects_invalid_or_missing_remote() -> None:
    allowlist = ("203.0.113.0/24",)
    server = TopggWebhookServer(
        TopggWebhookConfig(
            secret=_SECRET,
            host="127.0.0.1",
            port=8080,
            path="/noodswap/topgg-vote-webhook",
            allowed_ip_networks=allowlist,
        )
    )
    assert not _is_request_ip_allowed(None, server._allowed_networks)
    assert not _is_request_ip_allowed("not-an-ip", server._allowed_networks)


def test_is_request_ip_allowed_checks_cidr_membership() -> None:
    allowlist = ("203.0.113.0/24",)
    server = TopggWebhookServer(
        TopggWebhookConfig(
            secret=_SECRET,
            host="127.0.0.1",
            port=8080,
            path="/noodswap/topgg-vote-webhook",
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
            secret=_SECRET,
            host="127.0.0.1",
            port=8080,
            path="/noodswap/topgg-vote-webhook",
            expected_bot_id="",
        )
    )
    try:
        yield server
    finally:
        storage.DB_PATH = original_db_path
        tmp_dir.cleanup()


async def test_rejects_request_with_invalid_signature(webhook_server: TopggWebhookServer) -> None:
    body = _vote_body("123")
    request = make_mocked_request(
        "POST",
        "/noodswap/topgg-vote-webhook",
        headers={
            "Content-Type": "application/json",
            "x-topgg-signature": "t=1700000000,v1=badsignature",
        },
    )
    request.read = AsyncMock(return_value=body)

    response = await webhook_server._handle_vote(request)

    assert response.status == 401


async def test_rejects_request_with_missing_signature(webhook_server: TopggWebhookServer) -> None:
    body = _vote_body("123")
    request = make_mocked_request(
        "POST",
        "/noodswap/topgg-vote-webhook",
        headers={"Content-Type": "application/json"},
    )
    request.read = AsyncMock(return_value=body)

    response = await webhook_server._handle_vote(request)

    assert response.status == 401


async def test_claims_vote_reward_on_valid_payload(webhook_server: TopggWebhookServer) -> None:
    body = _vote_body("123")
    response = await webhook_server._handle_vote(_mocked_post("/noodswap/topgg-vote-webhook", body))

    assert response.status == 200
    assert storage.get_player_starter(0, 123) == VOTE_STARTER_REWARD
    assert storage.get_player_votes(0, 123) == 1


async def test_duplicate_vote_claims_reward_each_time(webhook_server: TopggWebhookServer) -> None:
    body = _vote_body("456")
    first_response = await webhook_server._handle_vote(_mocked_post("/noodswap/topgg-vote-webhook", body))
    second_response = await webhook_server._handle_vote(_mocked_post("/noodswap/topgg-vote-webhook", body))

    assert first_response.status == 200
    assert second_response.status == 200
    assert storage.get_player_starter(0, 456) == VOTE_STARTER_REWARD * 2
    assert storage.get_player_votes(0, 456) == 2


async def test_rejects_non_json_content_type_when_enforced(webhook_server: TopggWebhookServer) -> None:
    body = _vote_body("123")
    response = await webhook_server._handle_vote(
        _mocked_post("/noodswap/topgg-vote-webhook", body, content_type="text/plain")
    )

    assert response.status == 415


async def test_rejects_payload_too_large_from_content_length(webhook_server: TopggWebhookServer) -> None:
    body = _vote_body("123")
    response = await webhook_server._handle_vote(
        _mocked_post(
            "/noodswap/topgg-vote-webhook",
            body,
            extra_headers={"Content-Length": "999999"},
        )
    )

    assert response.status == 413


async def test_acknowledges_webhook_test_type_without_claiming_reward(webhook_server: TopggWebhookServer) -> None:
    body = _test_body("123")
    response = await webhook_server._handle_vote(_mocked_post("/noodswap/topgg-vote-webhook", body))

    assert response.status == 200
    assert storage.get_player_starter(0, 123) == 0
    assert storage.get_player_votes(0, 123) == 0


async def test_rejects_unknown_vote_type(webhook_server: TopggWebhookServer) -> None:
    raw = json_module.dumps(
        {"type": "mystery", "data": {"user": {"platform_id": "123"}}}
    ).encode()
    response = await webhook_server._handle_vote(_mocked_post("/noodswap/topgg-vote-webhook", raw))

    assert response.status == 400
    assert storage.get_player_starter(0, 123) == 0
    assert storage.get_player_votes(0, 123) == 0


async def test_rejects_unexpected_project_platform_id() -> None:
    tmp_dir = tempfile.TemporaryDirectory()
    original_db_path = storage.DB_PATH
    storage.DB_PATH = Path(tmp_dir.name) / "test.db"
    storage.init_db()
    server = TopggWebhookServer(
        TopggWebhookConfig(
            secret=_SECRET,
            host="127.0.0.1",
            port=8080,
            path="/noodswap/topgg-vote-webhook",
            expected_bot_id="EXPECTED_BOT",
        )
    )
    try:
        body = _vote_body("123", bot_platform_id="OTHER_BOT")
        response = await server._handle_vote(_mocked_post("/noodswap/topgg-vote-webhook", body))
        assert response.status == 400
        assert storage.get_player_starter(0, 123) == 0
        assert storage.get_player_votes(0, 123) == 0
    finally:
        storage.DB_PATH = original_db_path
        tmp_dir.cleanup()
