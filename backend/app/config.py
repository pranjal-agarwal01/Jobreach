"""Settings from the environment (backend/.env in local development)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "")
    supabase_url: str = os.environ.get("SUPABASE_URL", "https://pksaqwmgibkuyydlwdfb.supabase.co")
    # Model per spec section 10.1. Cheaper models are a decision to measure, not assume.
    # On Microsoft Foundry this is the deployment name.
    model: str = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
    # "anthropic" (Claude API) or "foundry" (Microsoft Foundry: reads ANTHROPIC_FOUNDRY_RESOURCE
    # and ANTHROPIC_FOUNDRY_API_KEY). Foundry has no server-side fallbacks, so a refused request
    # is retried client-side on CLAUDE_FALLBACK_MODEL (a deployment name) when one is set.
    provider: str = os.environ.get("CLAUDE_PROVIDER", "anthropic").strip().lower()
    fallback_model: str = os.environ.get("CLAUDE_FALLBACK_MODEL", "").strip()
    cors_origins: list[str] = field(default_factory=lambda: _list(
        "CORS_ORIGINS", "http://localhost:3000"))
    worker_poll_seconds: float = float(os.environ.get("WORKER_POLL_SECONDS", "2"))
    consent_version: str = "2026-09-26"

    @property
    def jwks_url(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1"


settings = Settings()
