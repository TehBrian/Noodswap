import unittest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from aiohttp.test_utils import make_mocked_request

from noodswap import storage
from noodswap.topgg_webhook import (
    TopggWebhookConfig,
    TopggWebhookServer,
    _extract_user_id,
    _is_authorized,
    _is_request_ip_allowed,
    _normalize_route_path,
)


class TopggWebhookHelpersTests(unittest.TestCase):
    def test_normalize_route_path_prefixes_slash(self) -> None:
        self.assertEqual(_normalize_route_path("topgg/vote"), "/topgg/vote")

    def test_extract_user_id_accepts_numeric_string(self) -> None:
        self.assertEqual(_extract_user_id({"user": "123"}), 123)

    def test_extract_user_id_rejects_non_numeric_value(self) -> None:
        self.assertIsNone(_extract_user_id({"user": "abc"}))

    def test_is_authorized_compares_header_to_secret(self) -> None:
        self.assertTrue(_is_authorized("secret", "secret"))
        self.assertFalse(_is_authorized("nope", "secret"))

    def test_is_request_ip_allowed_allows_when_no_allowlist(self) -> None:
        self.assertTrue(_is_request_ip_allowed("203.0.113.5", ()))

    def test_is_request_ip_allowed_rejects_invalid_or_missing_remote(self) -> None:
        allowlist = ("203.0.113.0/24",)
        server = TopggWebhookServer(
            TopggWebhookConfig(
                secret="secret",
                host="127.0.0.1",
                port=8080,
                path="/noodswap/topgg-vote-webhook",
                allowed_ip_networks=allowlist,
            )
        )
        self.assertFalse(_is_request_ip_allowed(None, server._allowed_networks))
        self.assertFalse(_is_request_ip_allowed("not-an-ip", server._allowed_networks))

    def test_is_request_ip_allowed_checks_cidr_membership(self) -> None:
        allowlist = ("203.0.113.0/24",)
        server = TopggWebhookServer(
            TopggWebhookConfig(
                secret="secret",
                host="127.0.0.1",
                port=8080,
                path="/noodswap/topgg-vote-webhook",
                allowed_ip_networks=allowlist,
            )
        )
        self.assertTrue(_is_request_ip_allowed("203.0.113.25", server._allowed_networks))
        self.assertFalse(_is_request_ip_allowed("198.51.100.25", server._allowed_networks))


class TopggWebhookHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._original_db_path = storage.DB_PATH
        storage.DB_PATH = Path(self._tmp_dir.name) / "test.db"
        storage.init_db()
        self.server = TopggWebhookServer(
            TopggWebhookConfig(
                secret="secret",
                host="127.0.0.1",
                port=8080,
                path="/noodswap/topgg-vote-webhook",
                expected_bot_id="",
            )
        )

    async def asyncTearDown(self) -> None:
        storage.DB_PATH = self._original_db_path
        self._tmp_dir.cleanup()

    async def test_rejects_request_with_invalid_secret(self) -> None:
        request = make_mocked_request(
            "POST",
            "/noodswap/topgg-vote-webhook",
            headers={"Authorization": "wrong"},
        )
        request.json = AsyncMock(return_value={"user": "123"})

        response = await self.server._handle_vote(request)

        self.assertEqual(response.status, 401)

    async def test_claims_vote_reward_on_valid_payload(self) -> None:
        request = make_mocked_request(
            "POST",
            "/noodswap/topgg-vote-webhook",
            headers={"Authorization": "secret", "Content-Type": "application/json"},
        )
        request.json = AsyncMock(return_value={"user": "123"})

        response = await self.server._handle_vote(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(storage.get_player_starter(0, 123), 1)
        self.assertEqual(storage.get_player_votes(0, 123), 1)

    async def test_duplicate_vote_claims_reward_each_time(self) -> None:
        first_request = make_mocked_request(
            "POST",
            "/noodswap/topgg-vote-webhook",
            headers={"Authorization": "secret", "Content-Type": "application/json"},
        )
        first_request.json = AsyncMock(return_value={"user": "456"})

        second_request = make_mocked_request(
            "POST",
            "/noodswap/topgg-vote-webhook",
            headers={"Authorization": "secret", "Content-Type": "application/json"},
        )
        second_request.json = AsyncMock(return_value={"user": "456"})

        first_response = await self.server._handle_vote(first_request)

        second_response = await self.server._handle_vote(second_request)

        self.assertEqual(first_response.status, 200)
        self.assertEqual(second_response.status, 200)
        self.assertEqual(storage.get_player_starter(0, 456), 2)
        self.assertEqual(storage.get_player_votes(0, 456), 2)

    async def test_rejects_non_json_content_type_when_enforced(self) -> None:
        request = make_mocked_request(
            "POST",
            "/noodswap/topgg-vote-webhook",
            headers={"Authorization": "secret", "Content-Type": "text/plain"},
        )
        request.json = AsyncMock(return_value={"user": "123"})

        response = await self.server._handle_vote(request)

        self.assertEqual(response.status, 415)

    async def test_rejects_payload_too_large_from_content_length(self) -> None:
        request = make_mocked_request(
            "POST",
            "/noodswap/topgg-vote-webhook",
            headers={
                "Authorization": "secret",
                "Content-Type": "application/json",
                "Content-Length": "999999",
            },
        )
        request.json = AsyncMock(return_value={"user": "123"})

        response = await self.server._handle_vote(request)

        self.assertEqual(response.status, 413)
