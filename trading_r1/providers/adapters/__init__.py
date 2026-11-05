# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""Quirk adapters: per-model transforms of the chat-completion kwargs.

Most providers need none (the vanilla OpenAI kwargs work). An adapter exists
for the handful of dialects that differ: Qwen wants ``enable_thinking`` via
``chat_template_kwargs`` and a ``top_k``; reasoning models (the gpt-5 and gpt-6 families, Grok)
want ``max_completion_tokens`` instead of ``max_tokens`` and no ``temperature``; a strict
endpoint (Mistral, Cerebras) refuses ``stream_options`` or ``presence_penalty`` (``minimal``);
one with JSON mode but no schema enforcement (DeepSeek) takes the schema in the prompt
(``loose-json``).

An adapter is ``(kwargs: dict) -> dict`` and must not mutate its input. Selected
by ``ModelProfile.adapter``; ``None`` is identity.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trading_r1.providers.adapters.compat import loose_json_adapter, minimal_adapter
from trading_r1.providers.adapters.qwen import qwen_adapter
from trading_r1.providers.adapters.reasoning import reasoning_adapter

Adapter = Callable[[dict[str, Any]], dict[str, Any]]

_ADAPTERS: dict[str, Adapter] = {
    "qwen": qwen_adapter,
    "openai-reasoning": reasoning_adapter,
    "minimal": minimal_adapter,
    "loose-json": loose_json_adapter,
}


def apply_adapter(name: str | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Apply the named adapter to ``kwargs``; identity when name is falsy or
    unknown (an unknown name degrades gracefully rather than failing the call)."""
    if not name:
        return kwargs
    adapter = _ADAPTERS.get(name)
    return adapter(kwargs) if adapter is not None else kwargs


__all__ = [
    "Adapter",
    "apply_adapter",
    "loose_json_adapter",
    "minimal_adapter",
    "qwen_adapter",
    "reasoning_adapter",
]
