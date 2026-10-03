"""Verify Supabase access tokens (ES256, public keys from the project's JWKS)."""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)
_jwks: jwt.PyJWKClient | None = None


@dataclass(frozen=True)
class User:
    id: str
    email: str | None


def _jwks_client() -> jwt.PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = jwt.PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=3600)
    return _jwks


def verify_token(token: str) -> User:
    try:
        key = _jwks_client().get_signing_key_from_jwt(token)
        # leeway: a server whose clock runs a few seconds behind Supabase's would otherwise
        # reject a token issued a moment ago as "not yet valid".
        claims = jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience="authenticated",
                            issuer=settings.jwt_issuer, leeway=60)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token: {}".format(e)) from e
    if claims.get("role") != "authenticated" or not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not a signed-in user")
    return User(id=claims["sub"], email=claims.get("email"))


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return verify_token(creds.credentials)
