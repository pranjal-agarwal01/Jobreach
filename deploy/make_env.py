"""
Write deploy/.env, the server's settings, from the ones this PC already uses (backend/.env and
frontend/.env.local), with the addresses changed to the deployed site. Prints only the names
of the settings, never their values. deploy/.env is git-ignored; deploy/ship.sh copies it to
the server.

    python deploy/make_env.py [site domain]       (default: jobreach.pranjalagarwal.me)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "jobreach.pranjalagarwal.me"


def read(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


backend = read(ROOT / "backend" / ".env")
frontend = read(ROOT / "frontend" / ".env.local")
site = "https://" + DOMAIN
env = {k: v for k, v in backend.items() if v}
env.update({
    "SITE_DOMAIN": DOMAIN,
    "CORS_ORIGINS": site,
    "FRONTEND_URL": site,
    "PUBLIC_BASE_URL": site + "/api",           # resume share links and the Gmail return address
    "DB_POOL_MAX": "4",                          # the API and the worker share Supabase's pooler
    "NEXT_PUBLIC_SUPABASE_URL": frontend["NEXT_PUBLIC_SUPABASE_URL"],
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": frontend["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
})
env.pop("GMAIL_REDIRECT_URI", None)              # derived from PUBLIC_BASE_URL on the server

missing = [k for k in ("DATABASE_URL", "SUPABASE_URL", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
                       "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "TOKEN_ENCRYPTION_KEY") if not env.get(k)]
if missing:
    sys.exit("Missing in backend/.env: " + ", ".join(missing))

out = ROOT / "deploy" / ".env"
out.write_text("# Jobreach server settings. Secret: never commit (git-ignored).\n"
               + "".join("{}={}\n".format(k, v) for k, v in env.items()), encoding="utf-8", newline="\n")
print("Wrote {} with: {}".format(out.relative_to(ROOT), ", ".join(env)))
