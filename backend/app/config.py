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
FAST_STEPS = {"s1_extract", "s4_company", "discover_news"}


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
    # On Render the service's own public hostname is used when PUBLIC_BASE_URL is not set.
    public_base_url: str = (os.environ.get("PUBLIC_BASE_URL") or (
        "https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"] if os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        else "http://localhost:8000")).strip()
    # Gmail drafts (app/gmail.py): the Google Cloud OAuth client the person connects through,
    # and the key that encrypts each person's stored Gmail access (a Fernet key).
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    token_encryption_key: str = os.environ.get("TOKEN_ENCRYPTION_KEY", "").strip()
    # Until Google verifies the app, people see "Google hasn't verified this app" before the
    # consent screen, and the connect guide tells them what to press. Set to 1 once verified.
    google_app_verified: bool = os.environ.get("GOOGLE_APP_VERIFIED", "0").strip() in ("1", "true", "yes")
    # Database connections this process may hold. The API and the worker share Supabase's
    # pooler, so each is kept small.
    db_pool_max: int = int(os.environ.get("DB_POOL_MAX", "10"))
    worker_poll_seconds: float = float(os.environ.get("WORKER_POLL_SECONDS", "2"))
    # The shared pool (pool.py): the worker schedules a pool tick this often. It reads job boards
    # only while some user needs a kind of role, so an empty pool costs nothing.
    pool_enabled: bool = os.environ.get("POOL_ENABLED", "1").strip() not in ("0", "false", "no")
    pool_tick_minutes: int = int(os.environ.get("POOL_TICK_MINUTES", "15"))
    # Discovery (discover.py): new companies from Y Combinator's directory and funding news.
    discovery_enabled: bool = os.environ.get("DISCOVERY_ENABLED", "1").strip() not in ("0", "false", "no")
    # Strong, fresh matches prepared before the person opens them, per person per day.
    prewarm_per_day: int = int(os.environ.get("PREWARM_PER_DAY", "3"))
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
    def frontend_url(self) -> str:
        """Where the web app runs: the browser returns here after connecting Gmail."""
        return (os.environ.get("FRONTEND_URL") or self.cors_origins[0]).rstrip("/")

    @property
    def gmail_redirect_uri(self) -> str:
        """Google sends the browser back here; it must be listed on the OAuth client."""
        return os.environ.get("GMAIL_REDIRECT_URI") or self.public_base_url.rstrip("/") + "/gmail/callback"

    @property
    def jwks_url(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return self.supabase_url.rstrip("/") + "/auth/v1"


settings = Settings()
