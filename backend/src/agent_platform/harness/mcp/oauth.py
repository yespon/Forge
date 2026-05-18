"""OAuth token support for MCP HTTP/SSE servers.

Adapted from DeerFlow's MCP OAuth implementation.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OAuthConfig:
    """OAuth configuration for an MCP server."""
    token_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    grant_type: str = "client_credentials"
    scope: Optional[str] = None
    audience: Optional[str] = None
    refresh_token: Optional[str] = None
    extra_params: dict = field(default_factory=dict)
    token_field: str = "access_token"
    token_type_field: str = "token_type"
    expires_in_field: str = "expires_in"
    default_token_type: str = "Bearer"
    refresh_skew_seconds: int = 60
    enabled: bool = True


@dataclass
class _OAuthToken:
    access_token: str
    token_type: str
    expires_at: datetime


class OAuthTokenManager:
    """Acquire, cache, and refresh OAuth tokens for MCP servers."""

    def __init__(self):
        self._configs: dict[str, OAuthConfig] = {}
        self._tokens: dict[str, _OAuthToken] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def add_server(self, name: str, config: OAuthConfig) -> None:
        self._configs[name] = config
        self._locks[name] = asyncio.Lock()

    def has_oauth(self, server_name: str) -> bool:
        cfg = self._configs.get(server_name)
        return cfg is not None and cfg.enabled

    def has_any_oauth(self) -> bool:
        return any(c.enabled for c in self._configs.values())

    async def get_auth_header(self, server_name: str) -> Optional[str]:
        cfg = self._configs.get(server_name)
        if not cfg or not cfg.enabled:
            return None

        token = self._tokens.get(server_name)
        if token and token.expires_at > datetime.now(timezone.utc) + timedelta(seconds=cfg.refresh_skew_seconds):
            return f"{token.token_type} {token.access_token}"

        async with self._locks[server_name]:
            token = self._tokens.get(server_name)
            if token and token.expires_at > datetime.now(timezone.utc) + timedelta(seconds=cfg.refresh_skew_seconds):
                return f"{token.token_type} {token.access_token}"
            
            fresh = await self._fetch_token(cfg)
            self._tokens[server_name] = fresh
            logger.info("Refreshed OAuth token for MCP server %r", server_name)
            return f"{fresh.token_type} {fresh.access_token}"

    async def _fetch_token(self, cfg: OAuthConfig) -> _OAuthToken:
        data = {"grant_type": cfg.grant_type, **cfg.extra_params}
        if cfg.scope:
            data["scope"] = cfg.scope
        if cfg.audience:
            data["audience"] = cfg.audience
        if cfg.grant_type == "client_credentials":
            if not cfg.client_id or not cfg.client_secret:
                raise ValueError("client_credentials requires client_id and client_secret")
            data["client_id"] = cfg.client_id
            data["client_secret"] = cfg.client_secret
        elif cfg.grant_type == "refresh_token":
            if not cfg.refresh_token:
                raise ValueError("refresh_token grant requires refresh_token")
            data["refresh_token"] = cfg.refresh_token
            if cfg.client_id:
                data["client_id"] = cfg.client_id
            if cfg.client_secret:
                data["client_secret"] = cfg.client_secret
        else:
            raise ValueError(f"Unsupported grant_type: {cfg.grant_type}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cfg.token_url, data=data)
            resp.raise_for_status()
            payload = resp.json()

        access_token = payload.get(cfg.token_field)
        if not access_token:
            raise ValueError(f"OAuth response missing '{cfg.token_field}'")
        token_type = str(payload.get(cfg.token_type_field, cfg.default_token_type) or cfg.default_token_type)
        expires_in = int(payload.get(cfg.expires_in_field, 3600))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 1))
        return _OAuthToken(access_token=access_token, token_type=token_type, expires_at=expires_at)


def load_oauth_config_from_json(config_path: str) -> OAuthTokenManager:
    """Load OAuth configs from extensions_config.json."""
    import json
    from pathlib import Path
    mgr = OAuthTokenManager()
    p = Path(config_path)
    if not p.exists():
        return mgr
    try:
        data = json.loads(p.read_text())
        for name, srv in data.get("mcpServers", {}).items():
            oauth_raw = srv.get("oauth")
            if oauth_raw:
                cfg = OAuthConfig(
                    token_url=oauth_raw.get("token_url", ""),
                    client_id=oauth_raw.get("client_id", ""),
                    client_secret=oauth_raw.get("client_secret", ""),
                    grant_type=oauth_raw.get("grant_type", "client_credentials"),
                    scope=oauth_raw.get("scope"),
                    enabled=oauth_raw.get("enabled", True),
                )
                if cfg.token_url:
                    mgr.add_server(name, cfg)
    except Exception as e:
        logger.warning("Failed to load OAuth config: %s", e)
    return mgr


async def get_oauth_interceptor(oauth_mgr: OAuthTokenManager, server_name: str):
    """Build a callable interceptor that injects Authorization headers."""
    if not oauth_mgr.has_oauth(server_name):
        return None

    async def interceptor(request, handler):
        header = await oauth_mgr.get_auth_header(server_name)
        if not header:
            return await handler(request)
        headers = dict(getattr(request, "headers", {}) or {})
        headers["Authorization"] = header
        if hasattr(request, "override"):
            return await handler(request.override(headers=headers))
        return await handler(request)

    return interceptor
