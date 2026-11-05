# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""The model-agnostic backbone seam.

The loop talks to one normalized interface (:class:`Provider`, returning an
:class:`AssistantTurn`), and ``provider_for(profile)`` builds the right one for a
:class:`ModelProfile`. Each provider uses its backbone's most native path:
``chat`` (OpenAI-compatible Chat Completions: vLLM, Ollama, LM Studio, llama.cpp, the
hosted OpenAI-compatible APIs, and the page-reader), ``openai-responses`` (the OpenAI Responses
API: reasoning summaries + stateless threading), ``openai-codex`` (the same over a ChatGPT
subscription's Codex backend), ``gemini`` (the native google-genai SDK: structured thoughts +
thought_signature), ``anthropic`` (the Messages API). All surface reasoning/content deltas
through the same seam.

The lower-level ``complete()`` / ``stream()`` functions provide Chat Completions for
the page reader and summaries.
Provider-specific Chat Completions quirks live in pluggable adapters.

"""

import importlib
from typing import Any

from trading_r1.providers.base import AssistantTurn, Provider, ToolCall
from trading_r1.providers.client import build_create_kwargs, client_for, complete, stream
from trading_r1.providers.profiles import (
    DisplayMeta,
    Generation,
    ModelProfile,
    ProfileSelectionError,
    available_backbones,
    default_backbone_choice,
    default_backbone_name,
    get_profile,
    load_profiles,
)

# The wire protocols, by the name a profile gives in ``provider``. Loaded on first use: a native
# SDK is imported only by the profile that needs it.
PROTOCOLS: dict[str, str] = {
    "chat": "trading_r1.providers.chat:ChatCompletionsProvider",
    "openai-responses": "trading_r1.providers.openai:OpenAIProvider",
    "gemini": "trading_r1.providers.gemini:GeminiProvider",
    "anthropic": "trading_r1.providers.anthropic:AnthropicProvider",
    "openai-codex": "trading_r1.providers.chatgpt:ChatGPTProvider",
}


def provider_for(profile: ModelProfile, client: Any | None = None) -> Provider:
    """Build the :class:`Provider` for a profile: the class its ``provider`` names."""
    module, _, name = PROTOCOLS[profile.provider].partition(":")
    return getattr(importlib.import_module(module), name)(profile, client)


__all__ = [
    "AssistantTurn",
    "DisplayMeta",
    "Generation",
    "ModelProfile",
    "PROTOCOLS",
    "Provider",
    "ToolCall",
    "ProfileSelectionError",
    "available_backbones",
    "default_backbone_choice",
    "default_backbone_name",
    "build_create_kwargs",
    "client_for",
    "complete",
    "get_profile",
    "load_profiles",
    "provider_for",
    "stream",
]
