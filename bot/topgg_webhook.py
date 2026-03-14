import hashlib
import hmac
import ipaddress
import json
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import web

from .settings import VOTE_STARTER_REWARD
from .storage import claim_vote_reward

logger = logging.getLogger(__name__)
DEFAULT_TOPGG_WEBHOOK_MAX_BODY_BYTES = 16 * 1024
DEFAULT_DISCORDBOTLIST_WEBHOOK_MAX_BODY_BYTES = 16 * 1024
IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _normalize_route_path(path: str) -> str:
    normalized = path.strip() or "/noodswap/topgg-vote-webhook"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _normalize_route_path_with_default(path: str, default_path: str) -> str:
    normalized = path.strip() or default_path
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _extract_user_id(payload: dict[str, Any]) -> int | None:
    """Extract the Discord platform user ID from a webhooks v2 payload."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    user = data.get("user")
    if not isinstance(user, dict):
        return None
    raw_user = user.get("platform_id")
    if isinstance(raw_user, str) and raw_user.isdigit():
        return int(raw_user)
    if isinstance(raw_user, int) and raw_user >= 0:
        return int(raw_user)
    return None


def _extract_discordbotlist_user_id(payload: dict[str, Any]) -> int | None:
    raw_user = payload.get("id")
    if isinstance(raw_user, str) and raw_user.isdigit():
        return int(raw_user)
    if isinstance(raw_user, int) and raw_user >= 0:
        return int(raw_user)
    return None


def _verify_signature(raw_body: bytes, header_value: str | None, secret: str) -> bool:
    """Verify the x-topgg-signature header using the webhooks v2 HMAC-SHA256 scheme.

    The header format is: t={unix_timestamp},v1={hmac_sha256_hex}
    The HMAC message is: {timestamp}.{raw_body_bytes}
    """
    if not secret or not header_value:
        return False
    parts: dict[str, str] = {}
    for part in header_value.split(","):
        if "=" in part:
            k, _, v = part.partition("=")
            parts[k.strip()] = v.strip()
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    message = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _parse_networks(raw_networks: tuple[str, ...]) -> tuple[IpNetwork, ...]:
    parsed: list[IpNetwork] = []
    for raw in raw_networks:
        value = raw.strip()
        if not value:
            continue
        parsed.append(ipaddress.ip_network(value, strict=False))
    return tuple(parsed)


def _is_discordbotlist_authorized(header_value: str | None, secret: str) -> bool:
    if not secret or not header_value:
        return False
    return hmac.compare_digest(header_value.strip(), secret)


def _is_request_ip_allowed(remote: str | None, allowed_networks: tuple[IpNetwork, ...]) -> bool:
    if not allowed_networks:
        return True
    if not remote:
        return False
    try:
        address = ipaddress.ip_address(remote)
    except ValueError:
        return False
    return any(address in network for network in allowed_networks)


@dataclass(slots=True)
class TopggWebhookConfig:
    secret: str
    host: str
    port: int
    path: str
    expected_bot_id: str = ""
    max_body_bytes: int = DEFAULT_TOPGG_WEBHOOK_MAX_BODY_BYTES
    require_json_content_type: bool = True
    allowed_ip_networks: tuple[str, ...] = ()
    discordbotlist_secret: str = ""
    discordbotlist_path: str = "/noodswap/discordbotlist-vote-webhook"
    discordbotlist_max_body_bytes: int = DEFAULT_DISCORDBOTLIST_WEBHOOK_MAX_BODY_BYTES
    discordbotlist_require_json_content_type: bool = True
    discordbotlist_allowed_ip_networks: tuple[str, ...] = ()


class TopggWebhookServer:
    def __init__(self, config: TopggWebhookConfig) -> None:
        self._config = config
        self._topgg_allowed_networks = _parse_networks(config.allowed_ip_networks)
        self._discordbotlist_allowed_networks = _parse_networks(config.discordbotlist_allowed_ip_networks)
        self._runner: web.AppRunner | None = None
        self._site: web.BaseSite | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._config.secret or self._config.discordbotlist_secret)

    async def start(self) -> None:
        if not self.enabled:
            logger.warning(
                "vote webhooks are disabled because neither TOPGG_WEBHOOK_SECRET nor DISCORDBOTLIST_WEBHOOK_SECRET is set."
            )
            return

        if self._runner is not None:
            return

        max_body_size = max(
            1,
            self._config.max_body_bytes,
            self._config.discordbotlist_max_body_bytes,
        )
        app = web.Application(client_max_size=max_body_size)

        if self._config.secret:
            app.router.add_post(_normalize_route_path(self._config.path), self._handle_vote)
        if self._config.discordbotlist_secret:
            app.router.add_post(
                _normalize_route_path_with_default(
                    self._config.discordbotlist_path,
                    "/noodswap/discordbotlist-vote-webhook",
                ),
                self._handle_discordbotlist_vote,
            )

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self._config.host, port=self._config.port)
        await self._site.start()
        paths: list[str] = []
        if self._config.secret:
            paths.append(_normalize_route_path(self._config.path))
        if self._config.discordbotlist_secret:
            paths.append(
                _normalize_route_path_with_default(
                    self._config.discordbotlist_path,
                    "/noodswap/discordbotlist-vote-webhook",
                )
            )
        logger.info(
            "vote webhook server listening on %s:%s%s",
            self._config.host,
            self._config.port,
            "" if not paths else " routes=" + ", ".join(paths),
        )

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def _handle_vote(self, request: web.Request) -> web.Response:
        if not _is_request_ip_allowed(request.remote, self._topgg_allowed_networks):
            logger.warning(
                "Rejected top.gg webhook request from disallowed source ip=%s.",
                request.remote,
            )
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)

        if self._config.require_json_content_type and request.content_type != "application/json":
            return web.json_response({"ok": False, "error": "unsupported_media_type"}, status=415)

        if request.content_length is not None and request.content_length > self._config.max_body_bytes:
            return web.json_response({"ok": False, "error": "payload_too_large"}, status=413)

        try:
            raw_body = await request.read()
        except web.HTTPRequestEntityTooLarge:
            return web.json_response({"ok": False, "error": "payload_too_large"}, status=413)

        if not _verify_signature(raw_body, request.headers.get("x-topgg-signature"), self._config.secret):
            logger.warning("Rejected top.gg webhook request due to invalid signature.")
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

        try:
            payload = json.loads(raw_body)
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

        if self._config.expected_bot_id:
            data = payload.get("data")
            project = data.get("project") if isinstance(data, dict) else None
            payload_bot_id = str(project.get("platform_id", "")).strip() if isinstance(project, dict) else ""
            if payload_bot_id and payload_bot_id != self._config.expected_bot_id:
                logger.warning(
                    "Rejected top.gg webhook vote for unexpected bot id %s.",
                    payload_bot_id,
                )
                return web.json_response({"ok": False, "error": "unexpected_bot"}, status=400)

        user_id = _extract_user_id(payload)
        if user_id is None:
            return web.json_response({"ok": False, "error": "missing_user"}, status=400)

        payload_type = str(payload.get("type", "")).strip().lower()
        if payload_type not in {"vote.create", "webhook.test"}:
            return web.json_response({"ok": False, "error": "invalid_type"}, status=400)

        if payload_type == "webhook.test":
            logger.info("top.gg test webhook acknowledged for user_id=%s", user_id)
            return web.json_response(
                {
                    "ok": True,
                    "claimed": False,
                    "starter_total": None,
                    "event_type": "webhook.test",
                },
                status=200,
            )

        starter_total = claim_vote_reward(
            guild_id=0,
            user_id=user_id,
            reward_amount=VOTE_STARTER_REWARD,
            vote_provider="topgg",
            remote_ip=request.remote,
            webhook_path=_normalize_route_path(self._config.path),
            payload=payload,
        )
        logger.info(
            "top.gg vote reward claimed for user_id=%s starter_total=%s",
            user_id,
            starter_total,
        )
        return web.json_response(
            {
                "ok": True,
                "claimed": True,
                "starter_total": starter_total,
                "event_type": "vote.create",
            },
            status=200,
        )

    async def _handle_discordbotlist_vote(self, request: web.Request) -> web.Response:
        if not _is_request_ip_allowed(request.remote, self._discordbotlist_allowed_networks):
            logger.warning(
                "Rejected DiscordBotList webhook request from disallowed source ip=%s.",
                request.remote,
            )
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)

        if self._config.discordbotlist_require_json_content_type and request.content_type != "application/json":
            return web.json_response({"ok": False, "error": "unsupported_media_type"}, status=415)

        if request.content_length is not None and request.content_length > self._config.discordbotlist_max_body_bytes:
            return web.json_response({"ok": False, "error": "payload_too_large"}, status=413)

        if not _is_discordbotlist_authorized(
            request.headers.get("Authorization"),
            self._config.discordbotlist_secret,
        ):
            logger.warning("Rejected DiscordBotList webhook request due to invalid authorization header.")
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

        try:
            raw_body = await request.read()
        except web.HTTPRequestEntityTooLarge:
            return web.json_response({"ok": False, "error": "payload_too_large"}, status=413)

        try:
            payload = json.loads(raw_body)
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

        user_id = _extract_discordbotlist_user_id(payload)
        if user_id is None:
            return web.json_response({"ok": False, "error": "missing_user"}, status=400)

        starter_total = claim_vote_reward(
            guild_id=0,
            user_id=user_id,
            reward_amount=VOTE_STARTER_REWARD,
            vote_provider="discordbotlist",
            remote_ip=request.remote,
            webhook_path=_normalize_route_path_with_default(
                self._config.discordbotlist_path,
                "/noodswap/discordbotlist-vote-webhook",
            ),
            payload=payload,
        )
        logger.info(
            "DiscordBotList vote reward claimed for user_id=%s starter_total=%s",
            user_id,
            starter_total,
        )
        return web.json_response(
            {
                "ok": True,
                "claimed": True,
                "starter_total": starter_total,
                "event_type": "vote",
            },
            status=200,
        )
