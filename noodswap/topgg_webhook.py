import hmac
import ipaddress
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import web

from .settings import VOTE_STARTER_REWARD
from .storage import claim_vote_reward

logger = logging.getLogger(__name__)
DEFAULT_TOPGG_WEBHOOK_MAX_BODY_BYTES = 16 * 1024
IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _normalize_route_path(path: str) -> str:
    normalized = path.strip() or "/noodswap/topgg-vote-webhook"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _extract_user_id(payload: dict[str, Any]) -> int | None:
    raw_user = payload.get("user")
    if isinstance(raw_user, str) and raw_user.isdigit():
        return int(raw_user)
    if isinstance(raw_user, int) and raw_user >= 0:
        return raw_user
    return None


def _is_authorized(header_value: str | None, secret: str) -> bool:
    if not secret:
        return False
    provided = (header_value or "").strip()
    return hmac.compare_digest(provided, secret)


def _parse_networks(raw_networks: tuple[str, ...]) -> tuple[IpNetwork, ...]:
    parsed: list[IpNetwork] = []
    for raw in raw_networks:
        value = raw.strip()
        if not value:
            continue
        parsed.append(ipaddress.ip_network(value, strict=False))
    return tuple(parsed)


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


class TopggWebhookServer:
    def __init__(self, config: TopggWebhookConfig) -> None:
        self._config = config
        self._allowed_networks = _parse_networks(config.allowed_ip_networks)
        self._runner: web.AppRunner | None = None
        self._site: web.BaseSite | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._config.secret)

    async def start(self) -> None:
        if not self.enabled:
            logger.warning("top.gg webhook is disabled because TOPGG_WEBHOOK_SECRET is not set.")
            return

        if self._runner is not None:
            return

        app = web.Application(client_max_size=max(1, self._config.max_body_bytes))
        app.router.add_post(_normalize_route_path(self._config.path), self._handle_vote)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self._config.host, port=self._config.port)
        await self._site.start()
        logger.info(
            "top.gg webhook server listening on %s:%s%s",
            self._config.host,
            self._config.port,
            _normalize_route_path(self._config.path),
        )

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def _handle_vote(self, request: web.Request) -> web.Response:
        if not _is_request_ip_allowed(request.remote, self._allowed_networks):
            logger.warning("Rejected top.gg webhook request from disallowed source ip=%s.", request.remote)
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)

        if not _is_authorized(request.headers.get("Authorization"), self._config.secret):
            logger.warning("Rejected top.gg webhook request due to invalid authorization header.")
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

        if self._config.require_json_content_type and request.content_type != "application/json":
            return web.json_response({"ok": False, "error": "unsupported_media_type"}, status=415)

        if request.content_length is not None and request.content_length > self._config.max_body_bytes:
            return web.json_response({"ok": False, "error": "payload_too_large"}, status=413)

        try:
            payload = await request.json()
        except web.HTTPRequestEntityTooLarge:
            return web.json_response({"ok": False, "error": "payload_too_large"}, status=413)
        except Exception:  # pragma: no cover - aiohttp raises different decode errors
            return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

        if self._config.expected_bot_id:
            payload_bot_id = str(payload.get("bot", "")).strip()
            if payload_bot_id and payload_bot_id != self._config.expected_bot_id:
                logger.warning(
                    "Rejected top.gg webhook vote for unexpected bot id %s.",
                    payload_bot_id,
                )
                return web.json_response({"ok": False, "error": "unexpected_bot"}, status=400)

        user_id = _extract_user_id(payload)
        if user_id is None:
            return web.json_response({"ok": False, "error": "missing_user"}, status=400)

        starter_total = claim_vote_reward(
            guild_id=0,
            user_id=user_id,
            reward_amount=VOTE_STARTER_REWARD,
        )
        logger.info("top.gg vote reward claimed for user_id=%s starter_total=%s", user_id, starter_total)
        return web.json_response(
            {
                "ok": True,
                "claimed": True,
                "starter_total": starter_total,
            },
            status=200,
        )
