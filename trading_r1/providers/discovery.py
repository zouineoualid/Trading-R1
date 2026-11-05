# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""What a model server says about itself: the model it has loaded, and its context window.

A profile whose model is ``auto`` (LM Studio, llama.cpp: one loaded model, named by the user in
the app) takes the first model the server lists (:func:`resolve_model`). A profile states the
window when it is known (``ModelProfile.context_window``). Where the server
reports it, its provider asks instead (``Provider.context_window``): a vLLM server in ``/models``
(``max_model_len``), an Ollama server in ``/api/show``, Gemini in its model record. Hosted
OpenAI-compatible APIs report none. A failed question is not an
error: the profile stays as it is and the runtime's default applies.
"""

from __future__ import annotations

import time

import httpx

from trading_r1.providers import provider_for
from trading_r1.providers.profiles import AUTO_MODEL, ModelProfile

_TTL_S = 600.0
_PROBE_TIMEOUT_S = 3.0
_cache: dict[tuple[str | None, str], tuple[float, int | None]] = {}


async def served_models(profile: ModelProfile) -> list[str]:
    """The model ids the profile's endpoint lists, in its order; ``[]`` when it cannot be asked."""
    url, headers = provider_for(profile).models_request()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_S) as client:
            payload = (await client.get(url, headers=headers)).json()
        entries = payload.get("data") or []
        return [str(m["id"]) for m in entries if isinstance(m, dict) and "id" in m]
    except Exception:  # noqa: BLE001 (an unanswered question leaves the profile as it is)
        return []


async def resolve_model(profile: ModelProfile) -> ModelProfile:
    """The profile with ``auto`` replaced by the first model its server lists. A server that
    lists none, or does not answer, leaves ``auto`` (the readiness check then says so)."""
    if profile.model != AUTO_MODEL:
        return profile
    served = await served_models(profile)
    return profile.model_copy(update={"model": served[0]}) if served else profile


async def discover_context_window(profile: ModelProfile) -> int | None:
    """The window the server reports for the profile's model, or None when it reports none or
    cannot be asked. Answers are cached for ten minutes."""
    cached = _cache.get((profile.base_url, profile.model))
    if cached and time.monotonic() - cached[0] < _TTL_S:
        return cached[1]
    window: int | None = None
    try:
        window = await provider_for(profile).context_window()
    except Exception:  # noqa: BLE001 (an unanswered question leaves the profile as it is)
        window = None
    _cache[(profile.base_url, profile.model)] = (time.monotonic(), window)
    return window


async def with_context_window(profile: ModelProfile) -> ModelProfile:
    """The profile ready to call: its ``auto`` model resolved, and its window filled in from the
    server when it does not state one."""
    profile = await resolve_model(profile)
    if profile.context_window is not None:
        return profile
    window = await discover_context_window(profile)
    return profile if window is None else profile.model_copy(update={"context_window": window})
