"""Tests for the SQLite persistence layer (Final-Round SRS §8).

Pure-stdlib like the rest of the deterministic core: every test runs against an
in-memory database, so no file or dependency is touched.
"""

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hargaturun import db  # noqa: E402


def _deal_row(**overrides):
    """A complete, valid `deals` row; override single fields to probe a CHECK."""
    row = {
        "id": "d1",
        "item_name": "Roti Tawar",
        "shop_name": "Toko Sari Bakery",
        "category": "Bakery",
        "original_price": 15000,
        "deal_price": 10500,
        "discount_percent": 30,
        "days_remaining": 2.0,
        "initial_stock": 10,
        "remaining_stock": 10,
        "promo_copy": "Roti tawar fresh, diskon hari ini.",
        "status": "active",
        "created_at": "2026-08-21T04:15:00Z",
        "cost": 10000,
    }
    row.update(overrides)
    return row


_INSERT_DEAL = """
    INSERT INTO deals (id, item_name, shop_name, category, original_price,
        deal_price, discount_percent, days_remaining, initial_stock,
        remaining_stock, promo_copy, status, created_at, cost)
    VALUES (:id, :item_name, :shop_name, :category, :original_price,
        :deal_price, :discount_percent, :days_remaining, :initial_stock,
        :remaining_stock, :promo_copy, :status, :created_at, :cost)
"""

# The atomic claim step the CRUD layer will run inside BEGIN IMMEDIATE
# (SRS §7.4): decrement only while stock remains, and flip to sold_out at zero.
_CLAIM_UPDATE = """
    UPDATE deals
       SET remaining_stock = remaining_stock - 1,
           status = CASE WHEN remaining_stock - 1 = 0 THEN 'sold_out' ELSE status END
     WHERE id = ? AND status = 'active' AND remaining_stock > 0
"""


class _DbTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect_and_init(":memory:")
        self.addCleanup(self.conn.close)

    def _insert_deal(self, **overrides):
        self.conn.execute(_INSERT_DEAL, _deal_row(**overrides))


class TestSchemaInit(_DbTestCase):
    def test_tables_created(self):
        names = {
            r["name"]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertIn("deals", names)
        self.assertIn("claims", names)

    def test_indexes_created(self):
        names = {
            r["name"]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        self.assertIn("idx_deals_status", names)
        self.assertIn("idx_claims_deal_id", names)

    def test_foreign_keys_enabled(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_init_is_idempotent(self):
        db.init_db(self.conn)  # second call must not raise
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0], 0)


class TestDealsConstraints(_DbTestCase):
    def test_valid_deal_inserts(self):
        self._insert_deal()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0], 1)

    def test_cost_may_be_null(self):
        self._insert_deal(id="d-nocost", cost=None)
        got = self.conn.execute("SELECT cost FROM deals WHERE id = 'd-nocost'").fetchone()[0]
        self.assertIsNone(got)

    def test_negative_cost_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(cost=-1)

    def test_invalid_category_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(category="Elektronik")

    def test_invalid_status_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(status="paused")

    def test_remaining_above_initial_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(initial_stock=5, remaining_stock=6)

    def test_negative_remaining_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(remaining_stock=-1)

    def test_deal_price_above_original_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(original_price=10000, deal_price=12000)

    def test_discount_out_of_range_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_deal(discount_percent=150)


class TestClaimsConstraints(_DbTestCase):
    def setUp(self):
        super().setUp()
        self._insert_deal()

    def _insert_claim(self, **overrides):
        row = {
            "code": "HT-4821",
            "deal_id": "d1",
            "status": "claimed",
            "created_at": "2026-08-21T05:00:00Z",
            "redeemed_at": None,
        }
        row.update(overrides)
        self.conn.execute(
            """INSERT INTO claims (code, deal_id, status, created_at, redeemed_at)
               VALUES (:code, :deal_id, :status, :created_at, :redeemed_at)""",
            row,
        )

    def test_valid_claim_inserts(self):
        self._insert_claim()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 1)

    def test_unknown_deal_id_rejected_by_fk(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_claim(code="HT-0000", deal_id="ghost")

    def test_duplicate_code_rejected(self):
        self._insert_claim()
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_claim()  # same PK 'HT-4821'

    def test_redeemed_without_timestamp_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_claim(status="redeemed", redeemed_at=None)

    def test_claimed_with_timestamp_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_claim(status="claimed", redeemed_at="2026-08-21T06:00:00Z")

    def test_redeem_transition_ok(self):
        self._insert_claim()
        self.conn.execute(
            "UPDATE claims SET status = 'redeemed', redeemed_at = ? WHERE code = 'HT-4821'",
            ("2026-08-21T06:00:00Z",),
        )
        row = self.conn.execute(
            "SELECT status, redeemed_at FROM claims WHERE code = 'HT-4821'"
        ).fetchone()
        self.assertEqual(row["status"], "redeemed")
        self.assertIsNotNone(row["redeemed_at"])


class TestAtomicClaimPattern(_DbTestCase):
    """The stock guard the CRUD layer relies on to never oversell (F-FR-7)."""

    def setUp(self):
        super().setUp()
        self._insert_deal(initial_stock=1, remaining_stock=1)

    def test_claim_decrements_and_marks_sold_out(self):
        cur = self.conn.execute(_CLAIM_UPDATE, ("d1",))
        self.assertEqual(cur.rowcount, 1)
        row = self.conn.execute(
            "SELECT remaining_stock, status FROM deals WHERE id = 'd1'"
        ).fetchone()
        self.assertEqual(row["remaining_stock"], 0)
        self.assertEqual(row["status"], "sold_out")

    def test_second_claim_finds_no_stock(self):
        self.conn.execute(_CLAIM_UPDATE, ("d1",))          # stock 1 -> 0
        cur = self.conn.execute(_CLAIM_UPDATE, ("d1",))    # nothing left to claim
        self.assertEqual(cur.rowcount, 0)
        remaining = self.conn.execute(
            "SELECT remaining_stock FROM deals WHERE id = 'd1'"
        ).fetchone()[0]
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
