"""
Every model call goes through `structured()`: one request, a validated Pydantic result,
usage and cost logged per step (spec section 10). The pipeline never talks to a provider
directly, so switching provider or model is configuration (see config.py).

Providers:
  azure_openai  Azure OpenAI v1 API, Responses API with structured outputs (text_format)
  anthropic     Claude API, Messages API with structured outputs (output_format)
  foundry       Claude on Microsoft Foundry, same as anthropic through AnthropicFoundry

Shared conventions:
- Structured outputs for every step, validated against the step's schema.
- Stable prompt prefix first (rules, then the user's fact bank), volatile content (the
  post, the lead) last, so the provider's prompt cache can reuse the prefix. Claude caches
  at an explicit breakpoint; OpenAI caches prefixes automatically, steered by a cache key.
- Effort per step: low for extraction and screening, medium for selection and drafting.
- A refusal or a truncated answer raises before the content is read.
- Claude API: server-side fallbacks ("default"). Claude on Foundry: the SDK's client-side
  middleware. Nothing is sent to OpenAI to be stored (store=False).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Optional, Sequence, TypeVar

from pydantic import BaseModel

from .config import settings
from .db import system_tx

T = TypeVar("T", bound=BaseModel)

# USD per million tokens: (input, output, cache-read multiplier, cache-write multiplier).
# Checked 2026-10-01: platform.claude.com pricing (Foundry bills the same in CCUs) and
# developers.openai.com model pages (Azure Global Standard matches). Lookup matches by
# substring after "." becomes "-", most specific first, so deployment names still price.
PRICES = [
    ("gpt-6-1-sol", (2.0, 10.0, 0.05, 1.0)),
    ("gpt-6-sol", (2.0, 10.0, 0.10, 1.0)),
    ("gpt-6-luna", (0.10, 0.50, 0.10, 1.0)),
    ("gpt-6-astra", (10.0, 50.0, 0.10, 1.0)),
    ("fable-5-1", (10.0, 50.0, 0.025, 1.25)),
    ("fable", (10.0, 50.0, 0.10, 1.25)),
    ("opus-5-5", (4.0, 20.0, 0.05, 1.25)),
    ("opus", (5.0, 25.0, 0.10, 1.25)),
    ("sonnet-5", (2.0, 10.0, 0.10, 1.25)),     # Sonnet 5 and Sonnet 5.5
    ("sonnet", (3.0, 15.0, 0.10, 1.25)),
    ("haiku", (1.0, 5.0, 0.10, 1.25)),
]
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Thinking and reasoning tokens count against the output cap on every provider; a cap sized
# for the answer alone truncates it. No step asks for less than this.
MIN_OUTPUT_BUDGET = 8000


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    pass


@dataclass
class CallContext:
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    application_id: Optional[str] = None


@dataclass
class Usage:
    input_uncached: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0


def _price(model: str) -> tuple[float, float, float, float]:
    m = (model or "").lower().replace(".", "-")
    for key, price in PRICES:
        if key in m:
            return price
    return (5.0, 25.0, 0.10, 1.25)       # unknown: price high rather than under-report


def cost_usd(model: str, u: Usage) -> float:
    pin, pout, read_mult, write_mult = _price(model)
    return (u.input_uncached * pin + u.cache_write * pin * write_mult
            + u.cache_read * pin * read_mult + u.output * pout) / 1_000_000


# ------------------------------------------------------------------ clients

_client = None


def client():
    global _client
    if _client is None:
        if settings.provider == "azure_openai":
            import openai
            key = os.environ.get("AZURE_OPENAI_API_KEY")
            if not settings.azure_openai_endpoint or not key:
                raise LLMError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set (backend/.env)")
            _client = openai.OpenAI(base_url=settings.azure_openai_base_url, api_key=key)
        elif settings.provider == "foundry":
            import anthropic
            kw = {}
            if settings.fallback_model:
                kw["middleware"] = [anthropic.BetaRefusalFallbackMiddleware([{"model": settings.fallback_model}])]
            _client = anthropic.AnthropicFoundry(**kw)   # ANTHROPIC_FOUNDRY_RESOURCE / _API_KEY
        else:
            import anthropic
            _client = anthropic.Anthropic()              # ANTHROPIC_API_KEY
    return _client


def set_client(c) -> None:
    """Tests inject a fake client here."""
    global _client
    _client = c


# ------------------------------------------------------------------ providers

def _call_anthropic(model, schema, stable, volatile, effort, budget):
    import anthropic
    system = [{"type": "text", "text": s} for s in stable if s]
    if system:
        system[-1]["cache_control"] = {"type": "ephemeral"}
    extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if settings.provider == "anthropic" else {}
    try:
        resp = client().beta.messages.parse(
            model=model, max_tokens=budget, system=system,
            messages=[{"role": "user", "content": volatile}],
            output_format=schema, output_config={"effort": effort}, **extra)
    except anthropic.APIStatusError as e:
        raise LLMError("API error {}".format(e.status_code)) from e
    except anthropic.APIConnectionError as e:
        raise LLMError("connection error") from e
    u = resp.usage
    usage = Usage(input_uncached=getattr(u, "input_tokens", 0) or 0,
                  cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
                  cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
                  output=getattr(u, "output_tokens", 0) or 0)
    detail = getattr(getattr(resp, "stop_details", None), "category", None)
    return resp.parsed_output, usage, resp.stop_reason, getattr(resp, "model", model), detail


def _call_openai(model, schema, stable, volatile, effort, budget, cache_key):
    import openai
    try:
        resp = client().responses.parse(
            model=model, instructions="\n\n".join(s for s in stable if s), input=volatile,
            text_format=schema, reasoning={"effort": effort}, max_output_tokens=budget,
            prompt_cache_key=cache_key, store=False)
    except openai.APIStatusError as e:
        raise LLMError("API error {}".format(e.status_code)) from e
    except openai.APIConnectionError as e:
        raise LLMError("connection error") from e
    u = resp.usage
    details = getattr(u, "input_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    written = getattr(details, "cache_write_tokens", 0) or 0
    usage = Usage(input_uncached=max(0, (u.input_tokens or 0) - cached - written),
                  cache_write=written, cache_read=cached, output=u.output_tokens or 0)
    stop, detail = "end_turn", None
    if resp.status == "incomplete":
        reason = getattr(resp.incomplete_details, "reason", None)
        stop = "refusal" if reason == "content_filter" else "max_tokens"
        detail = reason
    for item in resp.output or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                stop, detail = "refusal", (getattr(part, "refusal", "") or "")[:120]
    return resp.output_parsed, usage, stop, getattr(resp, "model", model), detail


# ------------------------------------------------------------------ entry point

def _log(step: str, model: str, u: Usage, stop_reason: str, latency_ms: int, ctx: CallContext) -> None:
    with system_tx() as conn:
        conn.execute(
            """insert into llm_calls (user_id, job_id, application_id, step, model, input_tokens,
                   output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, latency_ms, stop_reason)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (ctx.user_id, ctx.job_id, ctx.application_id, step, model, u.input_uncached, u.output,
             u.cache_read, u.cache_write, round(cost_usd(model, u), 5), latency_ms, stop_reason))


def structured(step: str, output_format: type[T], *, stable: Sequence[str], volatile: str,
               effort: str = "low", max_tokens: int = 8000, ctx: CallContext | None = None,
               log: bool = True) -> T:
    """Run one step. `stable` blocks form the cached prefix (rules first, then per-user
    context such as the fact bank); `volatile` is the per-call message."""
    ctx = ctx or CallContext()
    model = settings.model_for(step)
    budget = max(max_tokens, MIN_OUTPUT_BUDGET)
    t0 = time.monotonic()
    try:
        if settings.provider == "azure_openai":
            # Same step + same user share a prefix; the key steers requests to the same cache.
            who = hashlib.sha256((ctx.user_id or "shared").encode()).hexdigest()[:12]
            parsed, usage, stop, served, detail = _call_openai(
                model, output_format, stable, volatile, effort, budget, "{}:{}".format(step, who))
        else:
            parsed, usage, stop, served, detail = _call_anthropic(
                model, output_format, stable, volatile, effort, budget)
    except LLMError as e:
        raise LLMError("{}: {}".format(step, e)) from e.__cause__
    latency = int((time.monotonic() - t0) * 1000)
    if log:
        _log(step, served or model, usage, stop, latency, ctx)

    if stop == "refusal":
        raise LLMRefusal("{}: declined ({})".format(step, detail))
    if stop == "max_tokens":
        raise LLMError("{}: output hit the {}-token cap".format(step, budget))
    if parsed is None:
        raise LLMError("{}: no structured output".format(step))
    return parsed


def dumps(obj) -> str:
    """Deterministic JSON for prompt blocks: sorted keys keep the cache prefix stable."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
