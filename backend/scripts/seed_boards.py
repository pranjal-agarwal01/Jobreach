"""
The pool's starting list of company job boards (docs/plan-global-pool.md, Phase 4). More are
found on their own: every company a user pastes a post from, once its site passes the company
check, has its careers page read, and a link to its Greenhouse, Lever or Ashby board adds it.

    python scripts/seed_boards.py                       # add the starting list (idempotent)
    python scripts/seed_boards.py --probe acme widgets  # which providers have a board by these names
    python scripts/seed_boards.py --add lever:acme:Acme:acme.com

Boards are public job feeds; adding one reads nothing until some user needs a kind of role.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import system_tx  # noqa: E402
from app.sources import boards  # noqa: E402

# (provider, board name, company, domain): boards with openings in India, checked 2026-10-02.
STARTING = [
    ("greenhouse", "groww", "Groww", "groww.in"),
    ("greenhouse", "inmobi", "InMobi", "inmobi.com"),
    ("greenhouse", "hackerrank", "HackerRank", "hackerrank.com"),
    ("greenhouse", "druva", "Druva", "druva.com"),
    ("greenhouse", "rubrik", "Rubrik", "rubrik.com"),
    ("greenhouse", "mongodb", "MongoDB", "mongodb.com"),
    ("greenhouse", "databricks", "Databricks", "databricks.com"),
    ("greenhouse", "gitlab", "GitLab", "gitlab.com"),
    ("greenhouse", "twilio", "Twilio", "twilio.com"),
    ("greenhouse", "coinbase", "Coinbase", "coinbase.com"),
    ("lever", "meesho", "Meesho", "meesho.com"),
    ("lever", "paytm", "Paytm", "paytm.com"),
    ("lever", "zeta", "Zeta", "zeta.tech"),
    ("lever", "cred", "CRED", "cred.club"),
    ("ashby", "atlan", "Atlan", "atlan.com"),
]


def add(rows: list[tuple[str, str, str, str]]) -> int:
    n = 0
    with system_tx() as conn:
        for source, token, name, domain in rows:
            c = conn.execute("""insert into companies (name, domain) values (%s, %s)
                                on conflict (domain) do update set name = companies.name returning id""",
                             (name, domain)).fetchone()
            r = conn.execute("""insert into source_boards (source, board_token, company_id) values (%s, %s, %s)
                                on conflict (source, board_token) do nothing returning id""",
                             (source, token, c["id"])).fetchone()
            n += 1 if r else 0
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", nargs="+")
    ap.add_argument("--add", nargs="+", help="provider:board:Company:domain")
    a = ap.parse_args()
    if a.probe:
        for name in a.probe:
            found = boards.probe(name)
            print(name, ", ".join("{} ({} openings)".format(s, n) for s, n in found) or "no board")
        return
    rows = [tuple(x.split(":", 3)) for x in a.add] if a.add else STARTING
    print("added {} new board(s) of {}".format(add(rows), len(rows)))


if __name__ == "__main__":
    main()
