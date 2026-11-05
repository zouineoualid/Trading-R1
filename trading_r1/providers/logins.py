# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""Logins an official client keeps on this machine, used as the credential of a subscription.

A subscription has no API key: its own client signs the user in and keeps the OAuth tokens in a
file. :func:`login_token` is the access token behind a credential name when the user has such a
login and did not set the variable: ``CHATGPT_ACCESS_TOKEN`` from the Codex CLI's ``codex login``
(``~/.codex/auth.json``, or ``$CODEX_HOME/auth.json``). The file is read again when it changes,
and when the access token has expired it is refreshed at OpenAI's OAuth endpoint and written
back, so the CLI's own login stays valid (a refresh token is good for one use).

Only ChatGPT is here. Anthropic's terms keep a Claude subscription to Claude Code and the Claude
apps, so Anthropic takes an API key; a Google AI subscription has no API of its own either.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from trading_r1.state.fileio import write_json

log = logging.getLogger(__name__)

CHATGPT_TOKEN = "CHATGPT_ACCESS_TOKEN"
CHATGPT_ACCOUNT = "CHATGPT_ACCOUNT_ID"
# The Codex CLI's OAuth client, at OpenAI's authorization server: a refresh token it issued is
# exchanged there for a new pair.
_TOKEN_URL = "https://auth.openai.com/oauth/token"
_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_ACCOUNT_CLAIM = "https://api.openai.com/auth"
_REFRESH_TIMEOUT_S = 30.0
_LEEWAY_S = 60.0

# the credential names a login stands behind, and which login
LOGIN_SOURCES: dict[str, str] = {CHATGPT_TOKEN: "codex"}


class LoginError(Exception):
    """A login that cannot be used or refreshed; the message says what to do."""


@dataclass(frozen=True)
class CodexLogin:
    """The tokens ``codex login`` left in ``auth.json``."""

    access_token: str
    refresh_token: str
    id_token: str
    account_id: str
    path: Path

    @property
    def expires_at(self) -> float | None:
        return expires_at(self.access_token)

    @property
    def expired(self) -> bool:
        return expired(self.access_token)


def codex_auth_path() -> Path:
    """``$CODEX_HOME/auth.json``, else ``~/.codex/auth.json``."""
    home = os.environ.get("CODEX_HOME")
    return (Path(home).expanduser() if home else Path.home() / ".codex") / "auth.json"


def jwt_claims(token: str) -> dict[str, Any]:
    """The payload of a JWT, unverified: it is the user's own token, read for its expiry and
    account id only. ``{}`` when the string is not a JWT."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def expires_at(token: str) -> float | None:
    """The token's ``exp`` as a POSIX time, or None when it states none."""
    exp = jwt_claims(token).get("exp")
    return float(exp) if isinstance(exp, int | float) else None


def expired(token: str, leeway_s: float = _LEEWAY_S) -> bool:
    """Whether the token has expired, or expires within ``leeway_s``. A token that states no
    expiry is taken as valid."""
    exp = expires_at(token)
    return exp is not None and exp - time.time() < leeway_s


def account_id_of(token: str) -> str:
    """The ChatGPT account id a Codex access token carries, or ""."""
    auth = jwt_claims(token).get(_ACCOUNT_CLAIM)
    account = auth.get("chatgpt_account_id") if isinstance(auth, dict) else None
    return account if isinstance(account, str) else ""


_cache: tuple[tuple[Any, ...], CodexLogin | None] | None = None


def codex_login(path: Path | None = None) -> CodexLogin | None:
    """The Codex CLI's login, or None when there is none (no file, or a file without tokens:
    Codex signed in with an API key, or keeps its login in the system keyring). Cached while the
    file is unchanged."""
    global _cache
    path = path or codex_auth_path()
    try:
        info = path.stat()
    except OSError:
        return None
    key = (str(path), info.st_mtime_ns, info.st_size, info.st_ino)
    if _cache is not None and _cache[0] == key:
        return _cache[1]
    login = _read(path)
    _cache = (key, login)
    return login


def _read(path: Path) -> CodexLogin | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        log.warning("Codex login not used: cannot read %s: %s", path, err)
        return None
    tokens = data.get("tokens") if isinstance(data, dict) else None
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        return None
    access = str(tokens["access_token"])
    account = tokens.get("account_id")
    return CodexLogin(
        access_token=access,
        refresh_token=str(tokens.get("refresh_token") or ""),
        id_token=str(tokens.get("id_token") or ""),
        account_id=account if isinstance(account, str) and account else account_id_of(access),
        path=path,
    )


async def refresh_codex_login(login: CodexLogin) -> CodexLogin:
    """Exchange the login's refresh token for a new pair at OpenAI's OAuth endpoint, and write
    the result back to its file (the refresh token is good for one use, so the CLI's copy must be
    the new one). Raises :class:`LoginError` when it cannot."""
    if not login.refresh_token:
        raise LoginError("the Codex login has no refresh token; run: codex login")
    body = {
        "client_id": _CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": login.refresh_token,
        "scope": "openid profile email",
    }
    try:
        async with httpx.AsyncClient(timeout=_REFRESH_TIMEOUT_S) as client:
            resp = await client.post(_TOKEN_URL, json=body)
    except httpx.HTTPError as err:
        raise LoginError(f"could not refresh the ChatGPT login: {err}") from err
    if resp.status_code != 200:
        raise LoginError(
            f"the ChatGPT login could not be refreshed (HTTP {resp.status_code}); run: codex login"
        )
    fresh = resp.json()
    access = fresh.get("access_token")
    if not isinstance(access, str) or not access:
        raise LoginError("the ChatGPT login could not be refreshed: no access token came back")
    refreshed = CodexLogin(
        access_token=access,
        refresh_token=str(fresh.get("refresh_token") or login.refresh_token),
        id_token=str(fresh.get("id_token") or login.id_token),
        account_id=login.account_id or account_id_of(access),
        path=login.path,
    )
    _write_back(refreshed)
    return refreshed


def _write_back(login: CodexLogin) -> None:
    """The file as it was, with the new tokens and refresh time; private to the owner."""
    global _cache
    try:
        data = json.loads(login.path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    tokens = dict(data.get("tokens") or {})
    tokens.update(
        {
            "access_token": login.access_token,
            "refresh_token": login.refresh_token,
            "id_token": login.id_token,
            "account_id": login.account_id,
        }
    )
    data["tokens"] = tokens
    data["last_refresh"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        write_json(login.path, data, private=True)
    except OSError as err:  # the new token still serves this process
        log.warning("the refreshed Codex login could not be written to %s: %s", login.path, err)
    _cache = None


def login_token(name: str) -> str:
    """The access token a login provides for credential ``name``, or "" when ``name`` is not a
    login's or the user has not signed in."""
    if LOGIN_SOURCES.get(name) != "codex":
        return ""
    login = codex_login()
    return login.access_token if login else ""


def login_names() -> set[str]:
    return set(LOGIN_SOURCES)
