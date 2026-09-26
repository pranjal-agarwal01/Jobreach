"""
Postgres access. Two kinds of transaction:

  user_tx(user_id)  runs as the `authenticated` role with the user's id in
                    request.jwt.claims, so every row-level security policy applies to
                    backend code exactly as it would to a direct API call. Use it for
                    anything that touches one user's data.
  system_tx()       runs as the connection's own role, for shared tables (companies, the
                    task queue, usage logs) and cross-user work.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set (backend/.env)")
        # prepare_threshold=None: server-side prepared statements break behind poolers.
        _pool = ConnectionPool(settings.database_url, min_size=1, max_size=10, open=True,
                               kwargs={"row_factory": dict_row, "prepare_threshold": None,
                                       "autocommit": False})
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def system_tx() -> Iterator[Connection]:
    with pool().connection() as conn:
        with conn.transaction():
            yield conn


@contextmanager
def user_tx(user_id: str) -> Iterator[Connection]:
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    with pool().connection() as conn:
        with conn.transaction():
            conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
            conn.execute("set local role authenticated")
            yield conn


def audit(user_id: str | None, action: str, detail: dict | None = None) -> None:
    """Record who did what, in its own transaction. Never put resume text, email bodies
    or other personal content in `detail`: ids and counts only."""
    with system_tx() as conn:
        conn.execute("insert into audit_log (user_id, action, detail) values (%s, %s, %s)",
                     (user_id, action, Jsonb(detail or {})))
