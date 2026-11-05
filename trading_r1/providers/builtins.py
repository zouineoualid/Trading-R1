# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""The built-in providers: one entry each for everything that names a model provider.

A provider is a hosted API, a subscription, or a self-served runtime: the backbone profile that
drives the loop, the reader profile that pairs with it, how it appears in the model menu, and
which environment variables (or which login) say the user has supplied it. ``profiles.py``
builds the built-in profiles from this list; adding a provider is one entry here (plus a
``Provider`` class when it speaks a new wire protocol: ``providers/__init__.PROTOCOLS``).

  hosted:        tauric (Tauric), gpt (OpenAI), anthropic (Anthropic), gemini (Google),
                 ollama-cloud (Ollama Cloud), openrouter, mistral, deepseek, xai (Grok), groq,
                 together, cerebras: need an API key
  subscription:  chatgpt (a ChatGPT plan, signed in with the Codex CLI): needs no key
  local:         vllm (Qwen via vLLM), ollama (Gemma via Ollama), lmstudio (LM Studio),
                 llamacpp (llama.cpp): keyless, self-served

When the user names none, the first provider they have supplied is used, in ``auto`` order; with
none supplied, no model is selected. Per-profile base_url/model are overridable via
TR1_<NAME>_BASE_URL / TR1_<NAME>_MODEL and the providers files. The local defaults expect a vLLM
serving `Qwen/Qwen3.8-27B-FP8` on loopback :8000, an Ollama on :11434, LM Studio on :1234 and a
llama.cpp server on :8080; LM Studio and llama.cpp serve whatever model is loaded (``auto``).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from trading_r1.providers.logins import CHATGPT_TOKEN, login_token

_TAURIC_BASE_URL = "https://api.tauric.ai/v1"
_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
_CHATGPT_BASE_URL = "https://chatgpt.com/backend-api/codex"  # a ChatGPT plan's Codex backend
_OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
_XAI_BASE_URL = "https://api.x.ai/v1"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_TOGETHER_BASE_URL = "https://api.together.xyz/v1"
_CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
_VLLM_BASE_URL = "http://127.0.0.1:8000/v1"
_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"  # local Ollama, OpenAI-compatible
_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"  # LM Studio's local server
_LLAMACPP_BASE_URL = "http://127.0.0.1:8080/v1"  # llama-server

AUTO = "auto"  # the model the server has loaded, whatever its name (providers/discovery.py)


@dataclass(frozen=True)
class BuiltinProvider:
    """A model provider as the product offers it."""

    name: str  # the backbone profile's name
    label: str  # the menu header
    kind: Literal["cloud", "local"]
    order: int  # the menu order (stable, independent of readiness)
    backbone: Mapping[str, Any]  # ModelProfile fields; the reader is named by `reader_profile`
    reader: Mapping[str, Any] | None = None  # the paired reader profile, when it is its own
    # Environment variables that say the user supplied this provider: its API key, or the URL of
    # the server they run. A subscription's token variable counts as set when its client's login
    # is on this machine (providers/logins.py).
    claimed_by: tuple[str, ...] = ()
    auto: int | None = None  # the rank when picking for a user who has supplied several
    # How to supply it when it is not an API key to enter (a sign-in); None: enter the key.
    setup: str | None = None

    def claimed(self, env: Mapping[str, str]) -> bool:
        return any(env.get(var) or login_token(var) for var in self.claimed_by)

    @property
    def key_env(self) -> str | None:
        """The variable that holds this provider's API key (or token), if it takes one."""
        return self.backbone.get("api_key_env") or next(
            (v for v in self.claimed_by if v.endswith(("_API_KEY", "_TOKEN"))), None
        )

    def profiles(self) -> dict[str, dict[str, Any]]:
        """The profile specs this provider contributes: the backbone (with its menu entry) and
        its reader when it has one of its own."""
        display = {"kind": self.kind, "provider_label": self.label, "order": self.order}
        out = {self.name: {**self.backbone, "name": self.name, "display": display}}
        if self.reader is not None:
            reader_name = self.backbone["reader_profile"]
            out[reader_name] = {**self.reader, "name": reader_name, "role": "reader"}
        return out


def _compat(
    name: str,
    label: str,
    *,
    order: int,
    auto: int,
    key: str,
    base_url: str,
    model: str,
    reader_model: str | None = None,
    adapter: str | None = None,
    reader_extra: Mapping[str, Any] | None = None,
) -> BuiltinProvider:
    """A hosted OpenAI-compatible Chat Completions API with an API key. The reader is a cheaper
    model of the same API when one is named, else the backbone reads its own pages."""
    backbone: dict[str, Any] = {
        "model": model,
        "base_url": base_url,
        "api_key_env": key,
        "reader_profile": f"{name}-reader" if reader_model or reader_extra else name,
    }
    if adapter:
        backbone["adapter"] = adapter
    reader: dict[str, Any] | None = None
    if reader_model or reader_extra:
        reader = {
            "model": reader_model or model,
            "base_url": base_url,
            "api_key_env": key,
            "generation": {"temperature": 0.0},
            **(reader_extra or {}),
        }
        if adapter and "adapter" not in reader:
            reader["adapter"] = adapter
    return BuiltinProvider(
        name=name,
        label=label,
        kind="cloud",
        order=order,
        claimed_by=(key,),
        auto=auto,
        backbone=backbone,
        reader=reader,
    )


def _local(
    name: str,
    label: str,
    *,
    order: int,
    auto: int,
    base_url: str,
    model: str = AUTO,
) -> BuiltinProvider:
    """A self-served OpenAI-compatible runtime that serves one loaded model and reads its own
    pages. Supplied when the user names its address or model."""
    return BuiltinProvider(
        name=name,
        label=label,
        kind="local",
        order=order,
        claimed_by=(f"TR1_{name.upper()}_BASE_URL", f"TR1_{name.upper()}_MODEL"),
        auto=auto,
        backbone={
            "model": model,
            "base_url": base_url,
            "api_key_literal": "EMPTY",
            "reader_profile": name,
            "generation": {"temperature": 0.7, "top_p": 0.95},
        },
    )


BUILTIN_PROVIDERS: tuple[BuiltinProvider, ...] = (
    # Tauric: the `tauric` model over Tauric's OpenAI-compatible inference API (Chat
    # Completions with function tools and streaming), on the same TAURIC_API_KEY as the data:
    # one registration gives a user both. It reads its own pages.
    BuiltinProvider(
        name="tauric",
        label="Tauric",
        kind="cloud",
        order=0,
        claimed_by=("TAURIC_API_KEY",),
        auto=4,
        backbone={
            "model": "tauric",
            "base_url": _TAURIC_BASE_URL,
            "api_key_env": "TAURIC_API_KEY",
            "reader_profile": "tauric",
            "output_limit": 16384,  # the inference API's ceiling per request
            "context_window": 262144,  # not reported by the API
        },
    ),
    BuiltinProvider(
        name="gpt",
        label="OpenAI",
        kind="cloud",
        order=10,
        claimed_by=("OPENAI_API_KEY",),
        auto=0,
        backbone={
            "model": "gpt-6.1-sol",
            # Native Responses API in the loop: streams reasoning summaries and threads
            # reasoning state statelessly (Chat Completions exposes no reasoning and 400s
            # on reasoning_effort+tools).
            "api_key_env": "OPENAI_API_KEY",
            "provider": "openai-responses",
            # Calls through complete() (Chat Completions) go via the reasoning adapter, which
            # handles that path's quirks (max_completion_tokens, no temp).
            "adapter": "openai-reasoning",
            "reader_profile": "gpt-reader",
            "context_window": 922000,  # the input limit its 400 reports; /models states none
        },
        # The cloud reader paired with the gpt backbone (reasoning model: max_completion_tokens,
        # no sampling params).
        reader={
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-6-luna",
            "adapter": "openai-reasoning",
        },
    ),
    # ChatGPT: the same OpenAI models on a ChatGPT plan instead of an API key, through the
    # Codex backend (providers/chatgpt.py). Supplied by the Codex CLI's login, or by a token in
    # CHATGPT_ACCESS_TOKEN. It reads its own pages (the backend has no Chat Completions).
    BuiltinProvider(
        name="chatgpt",
        label="ChatGPT",
        kind="cloud",
        order=12,
        claimed_by=(CHATGPT_TOKEN,),
        auto=1,
        setup=(
            "Sign in with the Codex CLI: run `codex login` (a ChatGPT Plus, Pro, Team or "
            f"Enterprise plan). Or set {CHATGPT_TOKEN} to an access token."
        ),
        backbone={
            "model": "gpt-6.1-sol",
            "provider": "openai-codex",
            "base_url": _CHATGPT_BASE_URL,
            "api_key_env": CHATGPT_TOKEN,
            "reader_profile": "chatgpt",
            "context_window": 922000,
        },
    ),
    # Anthropic: Claude over the Messages API (providers/anthropic.py), with Haiku as the reader.
    # The window is asked of the Models API. An API key only: Anthropic's terms keep a Claude
    # subscription to Claude Code and the Claude apps.
    BuiltinProvider(
        name="anthropic",
        label="Anthropic",
        kind="cloud",
        order=15,
        claimed_by=("ANTHROPIC_API_KEY",),
        auto=2,
        backbone={
            "model": "claude-sonnet-5-5",
            "provider": "anthropic",
            "base_url": _ANTHROPIC_BASE_URL,
            "api_key_env": "ANTHROPIC_API_KEY",
            "reader_profile": "anthropic-reader",
        },
        reader={
            "model": "claude-haiku-5-5",
            "provider": "anthropic",
            "base_url": _ANTHROPIC_BASE_URL,
            "api_key_env": "ANTHROPIC_API_KEY",
        },
    ),
    BuiltinProvider(
        name="gemini",
        label="Google",
        kind="cloud",
        order=20,
        claimed_by=("GEMINI_API_KEY",),
        auto=3,
        backbone={
            "model": "gemini-3.8-flash",
            # Native google-genai SDK in the loop: structured thoughts + thought_signature
            # threading (clean multi-turn tool calling). Needs GEMINI_API_KEY. base_url is the
            # OpenAI-compat endpoint, used only by the page reader's complete() path.
            "provider": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_env": "GEMINI_API_KEY",
            "reader_profile": "gemini",  # flash reads its own pages (compat path)
            "generation": {"temperature": 0.7, "top_p": 0.95},
        },
    ),
    # Ollama Cloud: Ollama's hosted models (an ollama.com account and its API key), over the
    # same OpenAI-compatible endpoint as a local Ollama. The reader thinks little.
    _compat(
        "ollama-cloud",
        "Ollama Cloud",
        order=22,
        auto=5,
        key="OLLAMA_API_KEY",
        base_url=_OLLAMA_CLOUD_BASE_URL,
        model="gpt-oss:120b",
        reader_extra={"extra_body": {"reasoning_effort": "low"}},
    ),
    # OpenRouter: one key for many models; the model id names the provider (`vendor/model`).
    _compat(
        "openrouter",
        "OpenRouter",
        order=23,
        auto=6,
        key="OPENROUTER_API_KEY",
        base_url=_OPENROUTER_BASE_URL,
        model="openai/gpt-oss-120b",
        reader_model="openai/gpt-oss-20b",
    ),
    # Mistral (La Plateforme): a strict endpoint, so the minimal request.
    _compat(
        "mistral",
        "Mistral",
        order=24,
        auto=7,
        key="MISTRAL_API_KEY",
        base_url=_MISTRAL_BASE_URL,
        model="mistral-large-latest",
        reader_model="mistral-small-latest",
        adapter="minimal",
    ),
    # DeepSeek: JSON mode without schema enforcement, so the reader's schema goes in the prompt.
    _compat(
        "deepseek",
        "DeepSeek",
        order=25,
        auto=8,
        key="DEEPSEEK_API_KEY",
        base_url=_DEEPSEEK_BASE_URL,
        model="deepseek-chat",
        reader_extra={"adapter": "loose-json"},
    ),
    # xAI: Grok's reasoning models take no sampling params (the reasoning adapter); the reader
    # is the non-reasoning variant.
    _compat(
        "xai",
        "xAI",
        order=26,
        auto=9,
        key="XAI_API_KEY",
        base_url=_XAI_BASE_URL,
        model="grok-4-1-fast-reasoning",
        reader_model="grok-4-1-fast-non-reasoning",
        adapter="openai-reasoning",
        reader_extra={"adapter": "minimal"},
    ),
    _compat(
        "groq",
        "Groq",
        order=27,
        auto=10,
        key="GROQ_API_KEY",
        base_url=_GROQ_BASE_URL,
        model="openai/gpt-oss-120b",
        reader_model="openai/gpt-oss-20b",
    ),
    # Together: its schema-constrained output has a shape of its own, so the reader's schema
    # goes in the prompt.
    _compat(
        "together",
        "Together",
        order=28,
        auto=11,
        key="TOGETHER_API_KEY",
        base_url=_TOGETHER_BASE_URL,
        model="openai/gpt-oss-120b",
        reader_extra={"adapter": "loose-json"},
    ),
    # Cerebras: a strict endpoint (no presence_penalty, no stream_options).
    _compat(
        "cerebras",
        "Cerebras",
        order=29,
        auto=12,
        key="CEREBRAS_API_KEY",
        base_url=_CEREBRAS_BASE_URL,
        model="gpt-oss-120b",
        adapter="minimal",
        reader_extra={},
    ),
    # vLLM: Qwen3.8-27B as the backbone (thinking on) and as its own reader (thinking off).
    # Sampling is the model card's for each mode. adapter="qwen" is the Qwen-model quirk
    # (thinking + top_k), not the backbone name; a non-Qwen TR1_VLLM_MODEL may need another.
    BuiltinProvider(
        name="vllm",
        label="vLLM",
        kind="local",
        order=30,
        claimed_by=("TR1_VLLM_BASE_URL",),
        auto=13,
        backbone={
            "model": "Qwen/Qwen3.8-27B-FP8",
            "base_url": _VLLM_BASE_URL,
            "api_key_literal": "EMPTY",
            "adapter": "qwen",  # thinking mode + top_k
            "reader_profile": "vllm-reader",  # the local reader
            "generation": {"temperature": 1.0, "top_p": 0.95},
        },
        reader={
            "model": "Qwen/Qwen3.8-27B-FP8",
            "base_url": _VLLM_BASE_URL,
            "api_key_literal": "EMPTY",
            # The reader does fast JSON extraction: thinking OFF (top_k via extra_body).
            "extra_body": {"top_k": 20, "chat_template_kwargs": {"enable_thinking": False}},
            "generation": {
                "temperature": 0.7,
                "top_p": 0.8,
                "presence_penalty": 1.5,
            },
        },
    ),
    # Ollama: a laptop/desktop local backbone (no GPU) over Ollama's OpenAI-compatible endpoint;
    # provider "chat", no adapter. The default model is a thinking model (gemma4:e4b): its
    # reasoning streams through the generic on_delta channel (client.py); the paired reader
    # turns thinking OFF so structured extraction isn't starved. Model/base_url overridable via
    # TR1_OLLAMA_MODEL / TR1_OLLAMA_BASE_URL (TR1_OLLAMA_MODEL=auto takes the first model pulled).
    BuiltinProvider(
        name="ollama",
        label="Ollama",
        kind="local",
        order=40,
        claimed_by=("TR1_OLLAMA_MODEL", "TR1_OLLAMA_BASE_URL"),
        auto=14,
        backbone={
            "model": "gemma4:e4b",
            "base_url": _OLLAMA_BASE_URL,
            "api_key_literal": "ollama",  # keyless local; OpenAI-compat placeholder
            "reader_profile": "ollama-reader",  # gemma reads its own pages, thinking off
            "generation": {"temperature": 0.7, "top_p": 0.95},
        },
        reader={
            "model": "gemma4:e4b",
            "base_url": _OLLAMA_BASE_URL,
            "api_key_literal": "ollama",
            # Thinking OFF for fast, deterministic JSON extraction (reasoning_effort=none is the
            # knob Ollama honors over the OpenAI endpoint; `think:false` is not plumbed there).
            "extra_body": {"reasoning_effort": "none"},
            "generation": {"temperature": 0.0, "top_p": 0.95},
        },
    ),
    # LM Studio and llama.cpp: the model loaded in the app, whatever its name (`auto`), on the
    # app's default port. TR1_LMSTUDIO_MODEL / TR1_LLAMACPP_MODEL name one when several are
    # loaded.
    _local("lmstudio", "LM Studio", order=42, auto=15, base_url=_LMSTUDIO_BASE_URL),
    _local("llamacpp", "llama.cpp", order=44, auto=16, base_url=_LLAMACPP_BASE_URL),
)


def builtin_profiles() -> dict[str, dict[str, Any]]:
    """Every provider's profile specs, by profile name."""
    return {name: spec for b in BUILTIN_PROVIDERS for name, spec in b.profiles().items()}


def supplied_provider(
    env: Mapping[str, str], among: Collection[str] | None = None
) -> BuiltinProvider | None:
    """The provider the user has supplied that a run is started on when they named none: the
    first by ``auto`` rank (a hosted API's key or a subscription's login, then a server they
    run), else None. ``among`` limits it to providers whose profile is usable."""
    supplied = [
        b
        for b in BUILTIN_PROVIDERS
        if b.auto is not None and b.claimed(env) and (among is None or b.name in among)
    ]
    return min(supplied, key=lambda b: b.auto or 0, default=None)


def model_keys() -> dict[str, str]:
    """Key variable name to the provider's label, in provider order."""
    return {b.key_env: b.label for b in BUILTIN_PROVIDERS if b.key_env}


def model_key_names() -> set[str]:
    return set(model_keys())


def setup_hints() -> dict[str, str]:
    """How to supply each provider that is not an API key to enter, by backbone name."""
    return {b.name: b.setup for b in BUILTIN_PROVIDERS if b.setup}
