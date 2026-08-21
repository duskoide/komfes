"""SQLite persistence bootstrap for the deal/claim marketplace loop.

Implements the storage side of the Final-Round SRS
(``docs/HargaTurun_Final_SRS.md`` §5, §8): a single local SQLite file accessed
through the standard-library ``sqlite3`` module — no separate database service.
This module owns exactly two things: opening a correctly-configured connection
and creating the schema. Deal CRUD, claim creation, and redemption (SRS §6.2,
§7) live in their own module.

Connection choices, and why:

* Foreign-key enforcement is OFF by default in SQLite and is a *per-connection*
  setting, so :func:`connect` turns it on every time — the ``claims.deal_id ->
  deals.id`` reference (SRS §8.2) is only real when it is enabled.
* ``isolation_level=None`` puts the connection in autocommit mode so the CRUD
  layer can drive its own explicit ``BEGIN IMMEDIATE`` transaction for the
  atomic "verify stock, decrement once, insert claim" step (SRS §7.4, F-FR-7).
  Left at the default, sqlite3's implicit transaction handling would open a
  deferred transaction and fight the explicit one.
* WAL journal mode lets a reader (consumer browsing ``/deals``) avoid blocking
  the writer (vendor claiming) during the local demo.
* ``busy_timeout`` makes a briefly-locked connection wait instead of raising,
  which keeps simultaneous local claims from failing spuriously.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Default location: a Docker-mounted volume so data survives API restarts
# (SRS §8). The API layer overrides this from its own configuration; tests pass
# ``":memory:"``.
DEFAULT_DB_PATH = Path("data/hargaturun.db")

# The schema ships next to this module as raw DDL, so it can be reviewed and
# diffed on its own (SRS §8).
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection configured for this application's guarantees.

    Pass ``":memory:"`` for a throwaway database in tests. For a file path, the
    parent directory is created if missing so first run works on a clean volume.
    """
    path = str(db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, isolation_level=None)  # autocommit; CRUD drives BEGIN IMMEDIATE
    conn.row_factory = sqlite3.Row                       # column access by name
    conn.execute("PRAGMA foreign_keys = ON;")            # per-connection; must be set every time
    conn.execute("PRAGMA journal_mode = WAL;")           # readers don't block the writer
    conn.execute("PRAGMA busy_timeout = 5000;")          # wait up to 5s on a lock, then error
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the tables and indexes if they do not exist.

    Idempotent — every statement in ``schema.sql`` uses ``IF NOT EXISTS``, so it
    is safe to call on every API startup.
    """
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def connect_and_init(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Convenience for app startup and tests: open a connection and ensure the
    schema exists, returning the ready-to-use connection."""
    conn = connect(db_path)
    init_db(conn)
    return conn
