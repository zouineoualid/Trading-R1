# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""Adapters for OpenAI-compatible APIs that reject part of the vanilla request.

``minimal`` drops the fields a strict endpoint refuses (Mistral and Cerebras 4xx on
``stream_options``; Cerebras and others on ``presence_penalty``). ``loose-json`` is for an
endpoint with JSON mode but no schema enforcement (DeepSeek): the schema goes into the system
message and ``response_format`` becomes ``json_object``. Both are pure (they return a new dict).
"""

from __future__ import annotations

import copy
import json
from typing import Any

_MINIMAL_DROP = ("presence_penalty", "stream_options")


def minimal_adapter(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Only the fields every OpenAI-compatible endpoint takes."""
    out = copy.deepcopy(kwargs)
    for key in _MINIMAL_DROP:
        out.pop(key, None)
    return out


def loose_json_adapter(kwargs: dict[str, Any]) -> dict[str, Any]:
    """A ``json_schema`` response format as JSON mode plus the schema in the prompt."""
    out = copy.deepcopy(kwargs)
    fmt = out.get("response_format") or {}
    if fmt.get("type") != "json_schema":
        return out
    schema = (fmt.get("json_schema") or {}).get("schema") or {}
    note = "Reply with one JSON object only, matching this JSON Schema exactly:\n" + json.dumps(
        schema
    )
    messages = list(out.get("messages") or [])
    for i, m in enumerate(messages):
        if m.get("role") == "system":
            messages[i] = {**m, "content": f"{m.get('content') or ''}\n\n{note}".strip()}
            break
    else:
        messages.insert(0, {"role": "system", "content": note})
    out["messages"] = messages
    out["response_format"] = {"type": "json_object"}
    return out
