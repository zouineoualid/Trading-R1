# Copyright 2026 Tauric Research
# SPDX-License-Identifier: Apache-2.0

"""`trading-r1 models`: every model provider, whether it is set up, whether it answers, and what
to do about one that is not.

The hosted APIs need a key (`trading-r1 secrets set NAME`, or the variable in the environment),
ChatGPT a sign-in with the Codex CLI, the local runtimes a running server; a local server is also
asked which models it serves, so a model name can be set with TR1_<NAME>_MODEL. No backend is
needed. Exit status 0 when at least one provider is ready, else 1.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from trading_r1.providers import ProfileSelectionError, available_backbones, load_profiles
from trading_r1.providers.health import endpoint_status, is_local
from trading_r1.providers.profiles import AUTO_MODEL, ModelProfile
from trading_r1.state.runtime_config import runtime_config


def _env_name(profile: ModelProfile, field: str) -> str:
    return f"TR1_{profile.name.upper().replace('-', '_')}_{field}"


async def _line(
    row: dict, profiles: dict[str, ModelProfile], client: httpx.AsyncClient
) -> tuple[bool, str, list[str]]:
    """``(ready, what to show, notes)`` for one backbone."""
    name = row["name"]
    if not row["configured"]:
        how = row.get("setup") or (
            f"set {row['api_key_env']} (trading-r1 secrets set {row['api_key_env']})"
        )
        return False, "not set up", [how]
    backbone = profiles[name]
    reader = profiles.get(backbone.reader_profile or "")
    local = is_local(backbone)
    b_status, ids = await endpoint_status(backbone, client, verify_model=local)
    notes: list[str] = []
    if local and ids:
        notes.append("serves: " + ", ".join(ids))
        if backbone.model == AUTO_MODEL:
            notes.append(f"{AUTO_MODEL} is the first: {ids[0]}")
    if b_status == "unreachable":
        fix = (
            f"start the {row['provider_label']} server, or set {_env_name(backbone, 'BASE_URL')}"
            if local
            else "the endpoint did not answer"
        )
        return False, "offline", notes + [fix]
    if b_status == "key_refused":
        return (
            False,
            "key refused",
            notes + ([row["setup"]] if row.get("setup") else [f"check {row['api_key_env']}"]),
        )
    if b_status == "model_missing":
        fix = (
            f"set {_env_name(backbone, 'MODEL')} to one of them, or {AUTO_MODEL} for the first"
            if ids
            else "load a model in it"
        )
        return False, f"does not serve {backbone.model}", notes + [fix]
    if reader is not None and reader.name != backbone.name:
        r_status, _ = await endpoint_status(reader, client, verify_model=is_local(reader))
        if r_status != "ok":
            return False, f"reader {reader.name} {r_status.replace('_', ' ')}", notes
    return True, "ready", notes


async def _run() -> int:
    try:
        rows = available_backbones()
        profiles = load_profiles()
    except ProfileSelectionError as err:
        print(err, file=sys.stderr)
        return 1
    async with httpx.AsyncClient(timeout=runtime_config().probe.timeout_s) as client:
        results = await asyncio.gather(*(_line(r, profiles, client) for r in rows))
    width = max(len(r["name"]) for r in rows)
    any_ready = False
    for row, (ready, status, notes) in zip(rows, results, strict=True):
        any_ready = any_ready or ready
        mark = "*" if ready else " "
        print(f"{mark} {row['name']:<{width}}  {row['provider_label']} ({row['kind']}): {status}")
        print(f"  {'':<{width}}  model {row['model']}")
        for note in notes:
            print(f"  {'':<{width}}  {note}")
    if not any_ready:
        print("\nno provider is ready; * marks one that is", file=sys.stderr)
    return 0 if any_ready else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="trading-r1 models", description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    return asyncio.run(_run())
