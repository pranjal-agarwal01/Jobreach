"""Settings from the environment (backend/.env in local development)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


# Default (main, fast) model per provider. "fast" runs the narrow, high-volume steps (reading
# a post, summarising a homepage); every other step uses "main". On Azure these are
# deployment names, so deploy them under these names or set LLM_MODEL / LLM_MODEL_FAST.
#
# Chosen 2026-10-01 under the founder's price constraint, in UAE North where Claude is not
# offered: GPT-6.1 Sol ($2 / $10 per MTok, cached input $0.10) for selection, drafting and
# onboarding; GPT-6 Luna ($0.10 / $0.50), OpenAI's model for "focused, high-volume tasks",
# for extraction. scripts/eval_extract.py measures whether Luna's extraction holds up.
DEFAULT_MODELS = {
    "azure_openai": ("gpt-6.1-sol", "gpt-6-luna"),
    "anthropic": ("claude-sonnet-5-5", ""),
    "foundry": ("claude-sonnet-5-5", ""),
}
FAST_STEPS = {"s1_extract", "s4_company"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "")
    supabase_url: str = os.environ.get("SUPABASE_URL", "https://pksaqwmgibkuyydlwdfb.supabase.co")
    # "azure_openai" (Azure OpenAI v1 API: AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY),
    # "anthropic" (Claude API: ANTHROPIC_API_KEY), or "foundry" (Claude on Microsoft Foundry:
    # ANTHROPIC_FOUNDRY_RESOURCE + ANTHROPIC_FOUNDRY_API_KEY).
    provider: str = (os.environ.get("LLM_PROVIDER") or os.environ.get("CLAUDE_PROVIDER")
                     or "anthropic").strip().lower()
    model: str = (os.environ.get("LLM_MODEL") or os.environ.get("CLAUDE_MODEL") or "").strip()
    model_fast: str = os.environ.get("LLM_MODEL_FAST", "").strip()
    azure_openai_endpoint: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    # Claude on Foundry has no server-side fallbacks, so a refused request is retried
    # client-side on this deployment when one is set.
    fallback_model: str = os.environ.get("CLAUDE_FALLBACK_MODEL", "").strip()
    cors_origins: list[str] = field(default_factory=lambda: _list(
        "CORS_ORIGINS", "http://localhost:3000"))
    # Where this API is reachable from outside: resume share links point here. Until the API
    # is deployed, links work only on this machine.
    public_base_url: str = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").strip()
    worker_poll_seconds: float = float(os.environ.get("WORKER_POLL_SECONDS", "2"))
    # Bump whenever the consent notice changes (2026-10-01: model processor is Azure OpenAI).
    consent_version: str = "2026-10-01"

    def model_for(self, step: str) -> str:
        main, fast = DEFAULT_MODELS.get(self.provider, DEFAULT_MODELS["anthropic"])
        main = self.model or main
        fast = self.model_fast or fast or main
        return fast if step in FAST_STEPS else main

    @property
    def azure_openai_base_url(self) -> str:
        """Accepts any endpoint Azure shows for the resource (https://<resource>.openai.azure.com/,
        .services.ai.azure.com/, .cognitiveservices.azure.com/, or a Foundry project endpoint
        ending /api/projects/<name>). The v1 API always lives at the host's /openai/v1/."""
        u = urlsplit(self.azure_openai_endpoint.strip())
        return f"{u.scheme}://{u.netloc}/openai/v1/" if u.netloc else ""

    @property
    def jwks_url(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1"


settings = Settings()
