# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""ChatGPT: a ChatGPT subscription (Plus, Pro, Team or Enterprise) as the backbone.

The subscription has no API key. The user signs in once with the Codex CLI (``codex login``), and
this provider uses that login (``providers/logins.py``) against the Codex backend at
``chatgpt.com/backend-api/codex``, which speaks the Responses API with a few rules of its own:
every request streams, ``store`` is false, the system prompt travels as ``instructions``, and
there is no ``max_output_tokens``. Everything else is the OpenAI Responses provider's: reasoning
summaries, encrypted reasoning threaded statelessly across tool calls, and function tools.

Each request carries the ChatGPT account id and an ``originator`` (the client name the backend
expects; ``TR1_CHATGPT_ORIGINATOR`` changes it). An access token that expired is refreshed
through the login and the call retried once. The backbone reads its own pages: ``complete()``
asks the Responses API for schema-constrained output.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import openai
from openai import AsyncOpenAI

from trading_r1.providers import logins
from trading_r1.providers.base import AssistantTurn, Completion, DeltaCallback
from trading_r1.providers.openai import (
    _INCLUDE,
    OpenAIProvider,
    _to_input,
    _to_tools,
    _turn_from_response,
)
from trading_r1.providers.profiles import ModelProfile
from trading_r1.providers.usage import record_openai

CHATGPT_BASE_URL = "https://chatgpt.com/backend-api/codex"
_DEFAULT_ORIGINATOR = "codex_cli_rs"
_BETA = "responses=experimental"
_NO_INSTRUCTIONS = "You are a helpful assistant."


class ChatGPTLoginError(RuntimeError):
    """The ChatGPT login is missing, expired and not refreshable, or refused."""


def _split_instructions(
    profile: ModelProfile, messages: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """The first system message as ``instructions`` (the backend wants the system prompt
    there), the rest as Responses input items (later system messages as developer items)."""
    instructions = _NO_INSTRUCTIONS
    rest: list[dict[str, Any]] = []
    taken = False
    for m in messages:
        if m.get("role") == "system" and not taken:
            instructions = str(m.get("content") or "") or _NO_INSTRUCTIONS
            taken = True
        elif m.get("role") == "system":
            rest.append({**m, "role": "developer"})
        else:
            rest.append(m)
    return instructions, _to_input(profile, rest)


class ChatGPTProvider(OpenAIProvider):
    """A ChatGPT subscription over the Codex backend (Responses API, streamed)."""

    def __init__(self, profile: ModelProfile, client: Any | None = None) -> None:
        super().__init__(profile, client)
        self._session_id = str(uuid.uuid4())
        self._login: logins.CodexLogin | None = None

    # -- credentials ---------------------------------------------------------------------

    def _token(self) -> tuple[str, str]:
        """``(access token, account id)``: the variables when set, else the Codex login."""
        token = self.profile.resolve_api_key()
        account = os.environ.get(logins.CHATGPT_ACCOUNT, "")
        login = logins.codex_login()
        if self._login is not None and self._login.path == (login.path if login else None):
            login = self._login  # the pair this provider refreshed, until the file changes
        if login and token == login.access_token:
            account = account or login.account_id
        return token, account or logins.account_id_of(token)

    def offline_status(self) -> str | None:
        """Readiness without a probe: the backend has no inventory to ask. A token that is valid
        or can be refreshed is ready; none, or one expired for good, reads as refused."""
        token, _ = self._token()
        if not token:
            return "key_refused"
        if not logins.expired(token):
            return "ok"
        login = logins.codex_login()
        refreshable = login is not None and login.access_token == token and login.refresh_token
        return "ok" if refreshable else "key_refused"

    async def _fresh_token(self) -> tuple[str, str]:
        """The token to call with, refreshed through the login when it has expired."""
        token, account = self._token()
        if not token:
            raise ChatGPTLoginError(
                "ChatGPT is not signed in: run `codex login` (the Codex CLI), or set "
                f"{logins.CHATGPT_TOKEN}"
            )
        if logins.expired(token):
            return await self._refresh(token)
        return token, account

    async def _refresh(self, token: str) -> tuple[str, str]:
        login = logins.codex_login()
        if login is None or login.access_token != token:
            raise ChatGPTLoginError(
                f"the ChatGPT token in {logins.CHATGPT_TOKEN} has expired; run `codex login` and "
                "unset it, or set a new one"
            )
        try:
            self._login = await logins.refresh_codex_login(login)
        except logins.LoginError as err:
            raise ChatGPTLoginError(str(err)) from err
        return self._login.access_token, self._login.account_id

    def _client(self, token: str, account: str) -> AsyncOpenAI:
        headers = {
            "OpenAI-Beta": _BETA,
            "originator": os.environ.get("TR1_CHATGPT_ORIGINATOR") or _DEFAULT_ORIGINATOR,
            "session_id": self._session_id,
        }
        if account:
            headers["chatgpt-account-id"] = account
        return AsyncOpenAI(
            api_key=token,
            base_url=self.profile.base_url or CHATGPT_BASE_URL,
            default_headers=headers,
            timeout=self.profile.timeout_s,
            max_retries=0,
        )

    # -- calls ---------------------------------------------------------------------------

    async def _stream(self, kwargs: dict[str, Any], on_delta: DeltaCallback | None) -> Any:
        """One streamed Responses call; a 401 refreshes the login and retries once."""
        if self.client is not None:
            return await self._consume(self.client, kwargs, on_delta)
        token, account = await self._fresh_token()
        try:
            return await self._consume(self._client(token, account), kwargs, on_delta)
        except openai.AuthenticationError:
            token, account = await self._refresh(token)
            return await self._consume(self._client(token, account), kwargs, on_delta)

    @staticmethod
    async def _consume(cl: Any, kwargs: dict[str, Any], on_delta: DeltaCallback | None) -> Any:
        async with cl.responses.stream(**kwargs) as stream:
            async for ev in stream:
                if on_delta is None:
                    continue
                if ev.type == "response.reasoning_summary_text.delta":
                    on_delta("reasoning", ev.delta)
                elif ev.type == "response.output_text.delta":
                    on_delta("content", ev.delta)
            return await stream.get_final_response()

    async def generate(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int,
        on_delta: DeltaCallback | None = None,
    ) -> AssistantTurn:
        instructions, items = _split_instructions(self.profile, messages)
        kwargs: dict[str, Any] = {
            "model": self.profile.model,
            "instructions": instructions,
            "input": items,
            "reasoning": {"effort": "high", "summary": "detailed"},
            "include": _INCLUDE,
            "store": False,
        }
        responses_tools = _to_tools(tools)
        if responses_tools:
            kwargs["tools"] = responses_tools
            kwargs["tool_choice"] = "auto"
        resp = await self._stream(kwargs, on_delta)
        record_openai(self.profile.name, resp)
        return _turn_from_response(self.profile, resp)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        response_schema: dict[str, Any] | None = None,
    ) -> Completion:
        """The page reader and summaries: one streamed call, no tools, the reply constrained to
        ``response_schema`` through the Responses ``text.format``."""
        instructions, items = _split_instructions(self.profile, messages)
        kwargs: dict[str, Any] = {
            "model": self.profile.model,
            "instructions": instructions,
            "input": items,
            "reasoning": {"effort": "low"},
            "store": False,
        }
        if response_schema is not None:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "output",
                    "schema": response_schema,
                    "strict": True,
                }
            }
        resp = await self._stream(kwargs, None)
        record_openai(self.profile.name, resp)
        turn = _turn_from_response(self.profile, resp)
        return Completion(turn.content, turn.finish_reason)
