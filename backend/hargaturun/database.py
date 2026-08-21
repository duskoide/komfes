from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS shops (
  phone TEXT PRIMARY KEY,
  shop_name TEXT NOT NULL,
  business_type TEXT NOT NULL,
  short_address TEXT
);
CREATE TABLE IF NOT EXISTS deals (
  id TEXT PRIMARY KEY,
  item_name TEXT NOT NULL,
  shop_name TEXT NOT NULL,
  category TEXT NOT NULL,
  original_price INTEGER NOT NULL,
  cost INTEGER NOT NULL,
  deal_price INTEGER NOT NULL,
  discount_percent INTEGER NOT NULL,
  days_remaining REAL NOT NULL,
  initial_stock INTEGER NOT NULL,
  remaining_stock INTEGER NOT NULL,
  promo_copy TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','sold_out','removed')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
  code TEXT PRIMARY KEY,
  deal_id TEXT NOT NULL REFERENCES deals(id),
  status TEXT NOT NULL CHECK(status IN ('claimed','redeemed')),
  created_at TEXT NOT NULL,
  redeemed_at TEXT
);
CREATE INDEX IF NOT EXISTS deals_status_idx ON deals(status);
CREATE INDEX IF NOT EXISTS claims_deal_idx ON claims(deal_id);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
