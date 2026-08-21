-- HargaTurun — marketplace persistence schema (SQLite)
-- Final-Round SRS (docs/HargaTurun_Final_SRS.md) §8.
--
-- Two tables only: `deals` and `claims`. There is intentionally no users/auth,
-- consumer, shop, analytics, daily-stock-log, or expiry table (SRS §2.2, §8).
--
-- Foreign-key enforcement is a per-connection PRAGMA set in db.py, not here:
-- SQLite does not persist `PRAGMA foreign_keys` in the schema file.

-- ---------------------------------------------------------------------------
-- deals: one row = one recommendation a vendor published as a live deal.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deals (
    id                TEXT    PRIMARY KEY,               -- UUIDv4 string
    item_name         TEXT    NOT NULL,
    shop_name         TEXT    NOT NULL DEFAULT '',       -- may be blank (SRS §8.1)
    category          TEXT    NOT NULL
                              CHECK (category IN (
                                  'Bakery', 'Prepared Food', 'Dairy', 'Beverage',
                                  'Produce', 'Snack', 'Canned', 'Other')),
    original_price    INTEGER NOT NULL CHECK (original_price > 0),   -- Rupiah, whole number
    deal_price        INTEGER NOT NULL CHECK (deal_price > 0),       -- validated engine value
    discount_percent  INTEGER NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
    days_remaining    REAL    NOT NULL CHECK (days_remaining >= 0),  -- display value only, no auto-expiry
    initial_stock     INTEGER NOT NULL CHECK (initial_stock > 0),
    remaining_stock   INTEGER NOT NULL
                              CHECK (remaining_stock >= 0
                                     AND remaining_stock <= initial_stock),
    promo_copy        TEXT    NOT NULL DEFAULT '',
    status            TEXT    NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'sold_out', 'removed')),
    created_at        TEXT    NOT NULL,                  -- ISO-8601 UTC, e.g. '2026-08-21T04:15:00Z'

    -- Cost per unit (Rupiah); NULL when the input never stated it. Lets the API
    -- enforce the engine margin floor on publish: deal_price >= cost + 500
    -- (SRS §7.1/§10; MIN_MARGIN_RP in pricing.py). Falls back to
    -- consistency-only checks when NULL.
    cost              INTEGER CHECK (cost IS NULL OR cost >= 0),

    CHECK (deal_price <= original_price)
);

-- GET /api/deals?status=active is the hot read path (SRS §7.2).
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals (status);

-- ---------------------------------------------------------------------------
-- claims: one row = one unit a consumer claimed. A claim reserves stock at
-- claim time; redemption confirms in-person collection and never decrements
-- stock a second time (SRS §4.3, §7.4, §7.5).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claims (
    code         TEXT    PRIMARY KEY,                    -- e.g. 'HT-4821'; uniqueness enforced by PK
    deal_id      TEXT    NOT NULL
                         REFERENCES deals (id),          -- no ON DELETE CASCADE: removal is soft (SRS §7.3)
    status       TEXT    NOT NULL DEFAULT 'claimed'
                         CHECK (status IN ('claimed', 'redeemed')),
    created_at   TEXT    NOT NULL,                       -- ISO-8601 UTC
    redeemed_at  TEXT,                                   -- NULL until redeemed
    -- Keep status and its timestamp consistent: redeemed rows carry a time,
    -- claimed rows do not.
    CHECK (
        (status = 'redeemed' AND redeemed_at IS NOT NULL) OR
        (status = 'claimed'  AND redeemed_at IS NULL)
    )
);

-- Listing claims for a deal (vendor verify view) and FK lookups.
CREATE INDEX IF NOT EXISTS idx_claims_deal_id ON claims (deal_id);
