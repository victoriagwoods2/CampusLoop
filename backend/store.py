"""SQLite persistence and clearly fictional, resettable demonstration records."""
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

from security import hash_password

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("CAMPUSLOOP_DB", ROOT / "data" / "campusloop.sqlite3"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
 password_hash TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), item_name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', category TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>=0),
 condition TEXT NOT NULL, defects TEXT NOT NULL DEFAULT '', area TEXT NOT NULL,
 available_from TEXT NOT NULL, pickup_deadline TEXT NOT NULL, pickup_windows TEXT NOT NULL DEFAULT '',
 time_from TEXT NOT NULL DEFAULT '', time_until TEXT NOT NULL DEFAULT '',
 requires_vehicle INTEGER NOT NULL DEFAULT 0, can_deliver INTEGER NOT NULL DEFAULT 0,
 dimensions TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'available',
 is_demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS needs (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), item_name TEXT NOT NULL,
 category TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0), arrival_date TEXT NOT NULL,
 available_from TEXT NOT NULL, available_until TEXT NOT NULL, area TEXT NOT NULL,
 time_from TEXT NOT NULL DEFAULT '', time_until TEXT NOT NULL DEFAULT '',
 has_vehicle INTEGER NOT NULL DEFAULT 0, preferred_condition TEXT NOT NULL DEFAULT '',
 essential_category TEXT NOT NULL DEFAULT '', requires_delivery INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'open', is_demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
 id TEXT PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES listings(id), need_id TEXT REFERENCES needs(id),
 recipient_id TEXT NOT NULL REFERENCES users(id), quantity INTEGER NOT NULL CHECK(quantity>0),
 status TEXT NOT NULL, transport_plan TEXT NOT NULL DEFAULT '', pickup_window TEXT NOT NULL DEFAULT '',
 pickup_agreed INTEGER NOT NULL DEFAULT 0,
 giver_confirmed INTEGER NOT NULL DEFAULT 0, recipient_confirmed INTEGER NOT NULL DEFAULT 0,
 is_demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), direction TEXT NOT NULL,
 listing_ids_json TEXT NOT NULL DEFAULT '[]', need_ids_json TEXT NOT NULL DEFAULT '[]',
 result_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_requests (
 id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plans(id), model TEXT NOT NULL,
 input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER,
 latency_ms INTEGER, tool_calls INTEGER NOT NULL, tool_names TEXT NOT NULL DEFAULT '[]',
 status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, category TEXT NOT NULL,
 accepted_items TEXT NOT NULL DEFAULT '', explicitly_excluded TEXT NOT NULL DEFAULT '',
 location TEXT NOT NULL DEFAULT 'New Haven area', notes TEXT NOT NULL,
 source_verified_on TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_listings_status_date ON listings(status, available_from, pickup_deadline);
CREATE INDEX IF NOT EXISTS idx_reservations_listing_status ON reservations(listing_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
"""

DEMO_USERS = [
    ("demo-outgoing", "outgoing@campusloop.demo", "Alex (demo giver)", "demo-outgoing"),
    ("demo-incoming", "incoming@campusloop.demo", "Jordan (demo recipient)", "demo-incoming"),
]

LISTINGS = [
    ("demo-pot", "demo-outgoing", "Cookware starter set", "Two saucepans, one skillet, and a spatula. Fictional demonstration listing.", "Kitchen", 1, "Good", "Small scuff on skillet base.", "East Rock", "2027-08-02", "2027-08-08", "Afternoons", 0, 0, "Fits in a tote", "available"),
    ("demo-lamp", "demo-outgoing", "Desk lamp", "Working LED desk lamp. Fictional demonstration listing.", "Lighting", 1, "Good", "Small mark on base.", "East Rock", "2027-08-02", "2027-08-08", "Afternoons", 0, 0, "12 in tall", "available"),
    ("demo-sofa", "demo-outgoing", "Small sofa", "Two-seat sofa. Fictional demonstration listing.", "Furniture", 1, "Fair", "Fabric wear on one arm.", "East Rock", "2027-08-02", "2027-08-05", "By arrangement", 1, 0, "70 × 34 × 31 in", "available"),
    ("demo-bookcase", "demo-outgoing", "Narrow bookcase", "Tall bookcase. Fictional demonstration listing.", "Furniture", 1, "Good", "", "East Rock", "2027-05-24", "2027-05-31", "Morning", 1, 0, "72 × 24 × 12 in", "available"),
    ("demo-towels", "demo-outgoing", "Bath towels", "Two clean towels; no current matching demo request. Fictional demonstration listing.", "Household", 2, "Good", "", "East Rock", "2027-08-02", "2027-08-07", "Afternoons", 0, 0, "Standard bath size", "available"),
    ("demo-reserved", "demo-outgoing", "Blue reading chair", "A chair already requested in this demo dataset. Fictional demonstration listing.", "Furniture", 1, "Good", "", "East Rock", "2027-08-02", "2027-08-08", "Afternoons", 0, 0, "30 × 30 × 34 in", "available"),
]

NEEDS = [
    ("demo-need-cookware", "demo-incoming", "Cookware", "Kitchen", 1, "2027-08-02", "2027-08-02", "2027-08-06", "East Rock", 0, "Fair", "Kitchen", 0),
    ("demo-need-lamp", "demo-incoming", "Desk lamp", "Lighting", 1, "2027-08-02", "2027-08-02", "2027-08-06", "East Rock", 0, "Fair", "Lighting", 0),
    ("demo-need-bookcase", "demo-incoming", "Bookcase", "Furniture", 1, "2027-08-02", "2027-08-02", "2027-08-06", "East Rock", 0, "Good", "Furniture", 0),
    ("demo-need-chair", "demo-incoming", "Reading chair", "Furniture", 1, "2027-08-02", "2027-08-02", "2027-08-06", "East Rock", 0, "Fair", "Furniture", 0),
]

RESOURCES = [
    ("resource-yale-sustainability", "Yale Graduate Housing Swap Room", "https://housing.yale.edu/graduate-housing/residence-life/sustainable-living/swap-room", "Graduate Housing reuse resource", "Clothing and shoes| Household and kitchen goods| Small appliances| Books, school, and office supplies| Toys and children’s items", "", "533 Prospect Street, basement level", "Commonly exchanged categories are examples and do not guarantee acceptance of every item. Hours vary throughout the year; check the Yale Connect community for current schedules and announcements. Contact: swaproom.whitehall@gmail.com. The page does not explicitly establish eligibility for graduate students living in private housing; confirm with the program.", ""),
    ("resource-city-recycling", "City of New Haven recycling and waste guidance", "https://www.newhavenct.gov/government/departments-divisions/public-works/recycling", "Municipal recycling guidance", "", "", "New Haven", "Official municipal source link. Check current item-specific rules and collection schedules.", ""),
    ("resource-habitat", "Habitat for Humanity of Greater New Haven ReStore", "https://habitatgnh.org/restore/", "Household-goods donation", "", "", "Greater New Haven", "Organization source link. Accepted items, condition rules, and pickup options have not been independently verified in this prototype.", ""),
]


def initialize() -> None:
    with connect() as db:
        db.executescript(SCHEMA)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(ai_requests)").fetchall()}
        if "tool_names" not in columns:
            db.execute("ALTER TABLE ai_requests ADD COLUMN tool_names TEXT NOT NULL DEFAULT '[]'")
        plan_columns = {row["name"] for row in db.execute("PRAGMA table_info(plans)").fetchall()}
        if "listing_ids_json" not in plan_columns:
            db.execute("ALTER TABLE plans ADD COLUMN listing_ids_json TEXT NOT NULL DEFAULT '[]'")
        if "need_ids_json" not in plan_columns:
            db.execute("ALTER TABLE plans ADD COLUMN need_ids_json TEXT NOT NULL DEFAULT '[]'")
        reservation_columns = {row["name"] for row in db.execute("PRAGMA table_info(reservations)").fetchall()}
        if "pickup_agreed" not in reservation_columns:
            db.execute("ALTER TABLE reservations ADD COLUMN pickup_agreed INTEGER NOT NULL DEFAULT 0")
        seed_demo(db)
        # Refresh this single source record while preserving all other resource rows.
        db.execute("""UPDATE resources SET name=?,url=?,category=?,accepted_items=?,explicitly_excluded=?,location=?,notes=?,source_verified_on=''
          WHERE id='resource-yale-sustainability'""", RESOURCES[0][1:8])


def seed_demo(db: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for user_id, email, name, password in DEMO_USERS:
        db.execute("INSERT OR IGNORE INTO users(id,email,display_name,password_hash,is_demo,created_at) VALUES(?,?,?,?,1,?)", (user_id, email, name, hash_password(password), now))
    for item in LISTINGS:
        (id_, user, name, desc, category, qty, cond, defects, area, start, end, windows, vehicle, deliver, dims, status) = item
        db.execute("""INSERT OR IGNORE INTO listings
            (id,user_id,item_name,description,category,quantity,condition,defects,area,available_from,pickup_deadline,pickup_windows,requires_vehicle,can_deliver,dimensions,status,is_demo,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""", (id_, user, name, desc, category, qty, cond, defects, area, start, end, windows, vehicle, deliver, dims, status, now))
    for need in NEEDS:
        (id_, user, name, cat, qty, arrival, start, end, area, car, condition, essential, delivery) = need
        db.execute("""INSERT OR IGNORE INTO needs
            (id,user_id,item_name,category,quantity,arrival_date,available_from,available_until,area,has_vehicle,preferred_condition,essential_category,requires_delivery,is_demo,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""", (*need, now))
    for resource in RESOURCES:
        db.execute("""INSERT OR IGNORE INTO resources(id,name,url,category,accepted_items,explicitly_excluded,location,notes,source_verified_on,is_demo)
          VALUES(?,?,?,?,?,?,?,?,?,0)""", resource)
    exists = db.execute("SELECT 1 FROM reservations WHERE id='demo-reservation-chair'").fetchone()
    if not exists:
        db.execute("""INSERT INTO reservations(id,listing_id,need_id,recipient_id,quantity,status,transport_plan,pickup_window,is_demo,created_at,updated_at)
          VALUES('demo-reservation-chair','demo-reserved','demo-need-chair','demo-incoming',1,'reserved','easy to carry','Afternoons',1,?,?)""", (now, now))


def remaining_quantity(db: sqlite3.Connection, listing_id: str) -> int:
    row = db.execute("SELECT quantity FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row:
        return 0
    held = db.execute("SELECT COALESCE(SUM(quantity),0) AS n FROM reservations WHERE listing_id=? AND status IN ('requested','reserved')", (listing_id,)).fetchone()["n"]
    return max(0, int(row["quantity"]) - int(held))


def ensure_quantity_available(db: sqlite3.Connection, listing_id: str, requested: int) -> int:
    """Call inside BEGIN IMMEDIATE before inserting a pending reservation."""
    listing = db.execute("SELECT status FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not listing or listing["status"] != "available":
        raise ValueError("This listing is no longer available.")
    available = remaining_quantity(db, listing_id)
    if requested < 1 or available < requested:
        raise ValueError("Not enough quantity remains; another request may have taken it.")
    return available


def reset_demo(db: sqlite3.Connection) -> None:
    """Only reset demo-owned rows; caller checks cross-owned reservations first."""
    db.execute("DELETE FROM reservations WHERE is_demo=1")
    db.execute("DELETE FROM ai_requests WHERE plan_id IN (SELECT id FROM plans WHERE user_id IN (SELECT id FROM users WHERE is_demo=1))")
    db.execute("DELETE FROM plans WHERE user_id IN (SELECT id FROM users WHERE is_demo=1)")
    db.execute("DELETE FROM needs WHERE is_demo=1")
    db.execute("DELETE FROM listings WHERE is_demo=1")
    db.execute("DELETE FROM resources WHERE is_demo=1")
    seed_demo(db)
