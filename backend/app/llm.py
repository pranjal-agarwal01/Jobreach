"""
Every Claude call goes through `structured()`: one request, a validated Pydantic result,
usage and cost logged per step (spec section 10).

- Structured outputs for every step, validated against the step's schema.
- Stable prompt prefix first (rules, then the user's fact bank) with a cache breakpoint,
  volatile content (the post, the lead) last.
- Effort per step: low for extraction and screening, medium for ranking and selection,
  medium or high for drafting.
- Server-side fallbacks ("default") so a safety-classifier decline is retried on the
  recommended fallback model instead of failing the lead. On Microsoft Foundry, which has
  no server-side fallbacks, the SDK's client-side middleware does the same job.
- stop_reason is checked before the content is read.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional, Sequence, TypeVar

import anthropic
from pydantic import BaseModel

from .config import settings
from .db import system_tx

T = TypeVar("T", bound=BaseModel)

# USD per million tokens: (input, output, cache-read multiplier). Checked 2026-10-01 against
# platform.claude.com/docs/en/about-claude/pricing; Foundry bills the same rates in CCUs.
# Ordered most specific first: lookup matches by substring, so a Foundry deployment named
# e.g. "jobreach-sonnet-5-5" still prices correctly.
PRICES = [
    ("fable-5-1", (10.0, 50.0, 0.025)),
    ("fable", (10.0, 50.0, 0.10)),
    ("opus-5-5", (4.0, 20.0, 0.05)),
    ("opus", (5.0, 25.0, 0.10)),
    ("sonnet-5", (2.0, 10.0, 0.10)),      # Sonnet 5 and Sonnet 5.5
    ("sonnet", (3.0, 15.0, 0.10)),
    ("haiku", (1.0, 5.0, 0.10)),
]
CACHE_WRITE_MULT = 1.25                   # 5-minute cache writes
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _price(model: str) -> tuple[float, float, float]:
    m = (model or "").lower().replace(".", "-")
    for key, price in PRICES:
        if key in m:
            return price
    return _price(settings.model) if model != settings.model else (5.0, 25.0, 0.10)


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    pass


@dataclass
class CallContext:
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    application_id: Optional[str] = None


_client: Optional[anthropic.Anthropic] = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if settings.provider == "foundry":
            # Foundry: no server-side fallbacks, so register the SDK's client-side middleware.
            kw = {}
            if settings.fallback_model:
                kw["middleware"] = [anthropic.BetaRefusalFallbackMiddleware([{"model": settings.fallback_model}])]
            _client = anthropic.AnthropicFoundry(**kw)   # ANTHROPIC_FOUNDRY_RESOURCE / _API_KEY
        else:
            _client = anthropic.Anthropic()              # ANTHROPIC_API_KEY
    return _client


def _fallback_args() -> dict:
    """Server-side fallbacks exist on the Claude API only (Foundry uses the middleware)."""
    return {"betas": [FALLBACK_BETA], "fallbacks": "default"} if settings.provider != "foundry" else {}


def set_client(c) -> None:
    """Tests inject a fake client here."""
    global _client
    _client = c


def cost_usd(model: str, usage) -> float:
    pin, pout, read_mult = _price(model)
    uncached = getattr(usage, "input_tokens", 0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    return (uncached * pin + write * pin * CACHE_WRITE_MULT + read * pin * read_mult
            + out * pout) / 1_000_000


def _log(step: str, model: str, usage, stop_reason: str, latency_ms: int, ctx: CallContext) -> None:
    with system_tx() as conn:
        conn.execute(
            """insert into llm_calls (user_id, job_id, application_id, step, model, input_tokens,
                   output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, latency_ms, stop_reason)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (ctx.user_id, ctx.job_id, ctx.application_id, step, model,
             getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0,
             getattr(usage, "cache_read_input_tokens", 0) or 0,
             getattr(usage, "cache_creation_input_tokens", 0) or 0,
             round(cost_usd(model, usage), 5), latency_ms, stop_reason))


def structured(step: str, output_format: type[T], *, stable: Sequence[str], volatile: str,
               effort: str = "low", max_tokens: int = 8000, ctx: CallContext | None = None,
               log: bool = True) -> T:
    """Run one step. `stable` blocks form the cached system prefix (rules first, then
    per-user context such as the fact bank); `volatile` is the per-call user message."""
    ctx = ctx or CallContext()
    system = [{"type": "text", "text": s} for s in stable if s]
    if system:
        system[-1]["cache_control"] = {"type": "ephemeral"}
    t0 = time.monotonic()
    try:
        resp = client().beta.messages.parse(
            model=settings.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": volatile}],
            output_format=output_format,
            output_config={"effort": effort},
            **_fallback_args(),
        )
    except anthropic.APIStatusError as e:
        raise LLMError("{}: API error {}".format(step, e.status_code)) from e
    except anthropic.APIConnectionError as e:
        raise LLMError("{}: connection error".format(step)) from e
    latency = int((time.monotonic() - t0) * 1000)
    if log:
        _log(step, getattr(resp, "model", settings.model), resp.usage, resp.stop_reason, latency, ctx)

    if resp.stop_reason == "refusal":
        category = getattr(getattr(resp, "stop_details", None), "category", None)
        raise LLMRefusal("{}: declined (category {})".format(step, category))
    if resp.stop_reason == "max_tokens":
        raise LLMError("{}: output hit max_tokens={}".format(step, max_tokens))
    parsed = resp.parsed_output
    if parsed is None:
        raise LLMError("{}: no structured output".format(step))
    return parsed


def dumps(obj) -> str:
    """Deterministic JSON for prompt blocks: sorted keys keep the cache prefix stable."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
