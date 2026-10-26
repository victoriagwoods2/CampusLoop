"""CampusLoop local API. Run with: uvicorn app:app --reload (from backend/)."""
import json
import os
import re
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import MODEL, run_agent
from core import evaluate_match, sanitize_public_text, validate_plan_input_size
from security import hash_password, new_session, session_hash, verify_password
from store import DB_PATH, connect, ensure_quantity_available, initialize, remaining_quantity, reset_demo

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(REPO_ROOT.parent / ".env", override=False)

app = FastAPI(title="CampusLoop API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173"), "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_selected_plans_stale(db: sqlite3.Connection, listing_ids=(), need_ids=()) -> None:
    """Invalidate plans when a selected record or their candidate pool changes."""
    changed_listings, changed_needs = set(listing_ids), set(need_ids)
    if not changed_listings and not changed_needs:
        return
    for row in db.execute("SELECT id,direction,listing_ids_json,need_ids_json FROM plans WHERE status='completed'").fetchall():
        selected_listings = set(json.loads(row["listing_ids_json"] or "[]"))
        selected_needs = set(json.loads(row["need_ids_json"] or "[]"))
        candidate_pool_changed = (bool(changed_listings) and row["direction"] == "move_in") or (bool(changed_needs) and row["direction"] == "move_out")
        if candidate_pool_changed or selected_listings & changed_listings or selected_needs & changed_needs:
            db.execute("UPDATE plans SET status='stale' WHERE id=?", (row["id"],))


def public_user(row) -> dict:
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "is_demo": bool(row["is_demo"])}


class RegisterInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=200)


class LoginInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class ListingInput(BaseModel):
    item_name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=600)
    category: str = Field(min_length=1, max_length=60)
    quantity: int = Field(ge=1, le=100)
    condition: str = Field(min_length=1, max_length=30)
    defects: str = Field(default="", max_length=240)
    area: str = Field(min_length=1, max_length=80)
    available_from: str
    pickup_deadline: str
    pickup_windows: str = Field(default="", max_length=160)
    time_from: str = Field(default="", max_length=5)
    time_until: str = Field(default="", max_length=5)
    requires_vehicle: bool = False
    can_deliver: bool = False
    dimensions: str = Field(default="", max_length=120)


class NeedInput(BaseModel):
    item_name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=60)
    quantity: int = Field(ge=1, le=100)
    arrival_date: str
    available_from: str
    available_until: str
    time_from: str = Field(default="", max_length=5)
    time_until: str = Field(default="", max_length=5)
    area: str = Field(min_length=1, max_length=80)
    has_vehicle: bool = False
    preferred_condition: str = Field(default="", max_length=30)
    essential_category: str = Field(default="", max_length=60)
    requires_delivery: bool = False


class PlanInput(BaseModel):
    direction: str
    listing_ids: list[str] = Field(default_factory=list, max_length=10)
    need_ids: list[str] = Field(default_factory=list, max_length=10)
    context: str = Field(default="", max_length=800)


class ReservationInput(BaseModel):
    listing_id: str
    need_id: Optional[str] = None
    quantity: int = Field(ge=1, le=100)
    transport_plan: str = Field(default="", max_length=120)
    pickup_window: str = Field(default="", max_length=160)


class DecisionInput(BaseModel):
    decision: str
    pickup_window: str = Field(default="", max_length=160)


class ConfirmInput(BaseModel):
    completed: bool = True


def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in to manage this record.")
    token = authorization[7:].strip()
    with connect() as db:
        row = db.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?", (session_hash(token), now())).fetchone()
    if not row:
        raise HTTPException(401, "Your session expired. Sign in again.")
    return public_user(row)


def _iso_date(value: str, label: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        raise HTTPException(422, f"{label} must be a date in YYYY-MM-DD format.")


def _validate_listing_dates(start: str, end: str) -> tuple[str, str]:
    a, b = _iso_date(start, "Available from"), _iso_date(end, "Pickup deadline")
    if b < a:
        raise HTTPException(422, "Pickup deadline must be on or after the available-from date.")
    return a, b


def _general_area(value: str) -> str:
    area = value.strip()
    if not area or sanitize_public_text(area, 80) != area:
        raise HTTPException(422, "Use a general neighborhood or pickup area; exact addresses and contact details are not allowed.")
    return area


def _validate_local_times(start: str, end: str, label: str) -> tuple[str, str]:
    if bool(start) != bool(end):
        raise HTTPException(422, f"Enter both the start and end of the {label} time range.")
    if start and (not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", start) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", end) or end < start):
        raise HTTPException(422, f"{label.capitalize()} times must be valid New Haven local times, with the end after the start.")
    return start, end


def _validate_pickup_window(window: str, earliest: str, latest: str, giver_from: str = "", giver_until: str = "", recipient_from: str = "", recipient_until: str = "") -> str:
    found = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?", window)
    if not found:
        raise HTTPException(422, "Choose a pickup date within the listing's available window.")
    pickup_date = _iso_date(found.group(1), "Pickup date")
    if pickup_date < earliest or pickup_date > latest:
        raise HTTPException(409, "The proposed pickup date is outside the overlap in both people's availability.")
    proposed_time = found.group(2) or ""
    for start, end in ((giver_from, giver_until), (recipient_from, recipient_until)):
        if start and end and (not proposed_time or not start <= proposed_time <= end):
            raise HTTPException(409, "Choose a pickup time inside both recorded local availability windows.")
    return proposed_time


def _listing_out(db: sqlite3.Connection, row) -> dict:
    d = dict(row)
    for field in ("item_name", "category", "description", "defects", "dimensions", "pickup_windows"):
        d[field] = sanitize_public_text(d.get(field, ""), 600 if field == "description" else 240)
    d["description"] = sanitize_public_text(d.get("description", ""))
    d["defects"] = sanitize_public_text(d.get("defects", ""), 240)
    remaining = remaining_quantity(db, d["id"])
    held = db.execute("SELECT status,COALESCE(SUM(quantity),0) AS n FROM reservations WHERE listing_id=? AND status IN ('requested','reserved') GROUP BY status", (d["id"],)).fetchall()
    statuses = {r["status"] for r in held}
    completed = db.execute("SELECT 1 FROM reservations WHERE listing_id=? AND status='completed' LIMIT 1", (d["id"],)).fetchone() is not None
    d["remaining_quantity"] = remaining
    d["is_demo"] = bool(d["is_demo"])
    d["requires_vehicle"] = bool(d["requires_vehicle"])
    d["can_deliver"] = bool(d["can_deliver"])
    d["public_status"] = d["status"] if d["status"] in {"withdrawn", "completed"} else ("reserved" if remaining == 0 and "reserved" in statuses else "requested" if remaining == 0 and "requested" in statuses else "completed" if remaining == 0 and completed else "available")
    return d


def _need_out(row) -> dict:
    d = dict(row)
    for field in ("item_name", "category", "essential_category"):
        d[field] = sanitize_public_text(d.get(field, ""), 120)
    d["has_vehicle"] = bool(d["has_vehicle"])
    d["requires_delivery"] = bool(d["requires_delivery"])
    d["is_demo"] = bool(d["is_demo"])
    return d


@app.on_event("startup")
def startup() -> None:
    initialize()


@app.get("/api/health")
def health():
    return {"ok": True, "database": str(DB_PATH.name), "ai_configured": bool(os.environ.get("PORTKEY_API_KEY")), "ai_model": MODEL, "ai_status": "configured; provider access not pre-verified" if os.environ.get("PORTKEY_API_KEY") else "unavailable: add PORTKEY_API_KEY to final project/.env or the parent directory's .env"}


@app.post("/api/auth/register")
def register(body: RegisterInput):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address.")
    user_id = str(uuid.uuid4())
    with connect() as db:
        try:
            db.execute("INSERT INTO users(id,email,display_name,password_hash,is_demo,created_at) VALUES(?,?,?,?,0,?)", (user_id, email, body.display_name.strip(), hash_password(body.password), now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with that email already exists.")
        token, token_digest = new_session()
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (token_digest, user_id, (datetime.now(timezone.utc)+timedelta(days=30)).isoformat()))
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return {"token": token, "user": public_user(row)}


@app.post("/api/auth/login")
def login(body: LoginInput):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Email or password is incorrect.")
        token, digest = new_session()
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (digest, row["id"], (datetime.now(timezone.utc)+timedelta(days=30)).isoformat()))
    return {"token": token, "user": public_user(row)}


@app.post("/api/auth/logout")
def logout(user=Header(default=None), authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (session_hash(authorization[7:].strip()),))
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=__import__("fastapi").Depends(current_user)):
    return user


@app.get("/api/listings")
def list_listings(mine: bool = False, category: str = "", q: str = "", user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        rows = db.execute("SELECT l.*,u.display_name,u.is_demo AS owner_is_demo FROM listings l JOIN users u ON u.id=l.user_id ORDER BY l.created_at DESC LIMIT 100").fetchall()
        out = []
        for row in rows:
            data = _listing_out(db, row)
            if mine and data["user_id"] != user["id"]:
                continue
            if not mine and data["status"] not in {"available", "withdrawn"}:
                continue
            if not mine and data["remaining_quantity"] < 1:
                continue
            if category and category.casefold() not in data["category"].casefold():
                continue
            if q and q.casefold() not in (data["item_name"] + " " + data["description"] + " " + data["area"]).casefold():
                continue
            data["owner_is_demo"] = bool(data["owner_is_demo"])
            out.append(data)
        return out


@app.post("/api/listings")
def create_listing(body: ListingInput, user=__import__("fastapi").Depends(current_user)):
    start, end = _validate_listing_dates(body.available_from, body.pickup_deadline)
    area = _general_area(body.area)
    time_from, time_until = _validate_local_times(body.time_from, body.time_until, "pickup")
    id_ = str(uuid.uuid4())
    with connect() as db:
        db.execute("""INSERT INTO listings(id,user_id,item_name,description,category,quantity,condition,defects,area,available_from,pickup_deadline,pickup_windows,time_from,time_until,requires_vehicle,can_deliver,dimensions,status,is_demo,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'available',?,?)""", (id_, user["id"], sanitize_public_text(body.item_name, 100), sanitize_public_text(body.description), sanitize_public_text(body.category, 60), body.quantity, sanitize_public_text(body.condition, 30), sanitize_public_text(body.defects, 240), area, start, end, sanitize_public_text(body.pickup_windows, 160), time_from, time_until, int(body.requires_vehicle), int(body.can_deliver), sanitize_public_text(body.dimensions, 120), int(user["is_demo"]), now()))
        _mark_selected_plans_stale(db, listing_ids=[id_])
        return _listing_out(db, db.execute("SELECT l.*,u.display_name,u.is_demo AS owner_is_demo FROM listings l JOIN users u ON u.id=l.user_id WHERE l.id=?", (id_,)).fetchone())


@app.patch("/api/listings/{listing_id}")
def edit_listing(listing_id: str, body: ListingInput, user=__import__("fastapi").Depends(current_user)):
    start, end = _validate_listing_dates(body.available_from, body.pickup_deadline)
    area = _general_area(body.area)
    time_from, time_until = _validate_local_times(body.time_from, body.time_until, "pickup")
    with connect() as db:
        row = db.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not row or row["user_id"] != user["id"]:
            raise HTTPException(404, "Listing not found.")
        if db.execute("SELECT 1 FROM reservations WHERE listing_id=? AND status IN ('requested','reserved')", (listing_id,)).fetchone():
            raise HTTPException(409, "Cancel or resolve active reservations before editing this listing.")
        db.execute("UPDATE listings SET item_name=?,description=?,category=?,quantity=?,condition=?,defects=?,area=?,available_from=?,pickup_deadline=?,pickup_windows=?,time_from=?,time_until=?,requires_vehicle=?,can_deliver=?,dimensions=? WHERE id=?", (sanitize_public_text(body.item_name, 100), sanitize_public_text(body.description), sanitize_public_text(body.category, 60), body.quantity, sanitize_public_text(body.condition, 30), sanitize_public_text(body.defects, 240), area, start, end, sanitize_public_text(body.pickup_windows, 160), time_from, time_until, int(body.requires_vehicle), int(body.can_deliver), sanitize_public_text(body.dimensions, 120), listing_id))
        _mark_selected_plans_stale(db, listing_ids=[listing_id])
        return _listing_out(db, db.execute("SELECT l.*,u.display_name,u.is_demo AS owner_is_demo FROM listings l JOIN users u ON u.id=l.user_id WHERE l.id=?", (listing_id,)).fetchone())


@app.post("/api/listings/{listing_id}/withdraw")
def withdraw_listing(listing_id: str, user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        row = db.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not row or row["user_id"] != user["id"]:
            raise HTTPException(404, "Listing not found.")
        if db.execute("SELECT 1 FROM reservations WHERE listing_id=? AND status IN ('requested','reserved')", (listing_id,)).fetchone():
            raise HTTPException(409, "Resolve active reservations before withdrawing this listing.")
        db.execute("UPDATE listings SET status='withdrawn' WHERE id=?", (listing_id,))
        _mark_selected_plans_stale(db, listing_ids=[listing_id])
    return {"ok": True}


@app.get("/api/needs")
def list_needs(mine: bool = False, user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        rows = db.execute("SELECT n.*,u.display_name,u.is_demo AS owner_is_demo FROM needs n JOIN users u ON u.id=n.user_id WHERE n.status='open' ORDER BY n.created_at DESC LIMIT 100").fetchall()
        return [{**_need_out(r), "display_name": r["display_name"], "owner_is_demo": bool(r["owner_is_demo"])} for r in rows if not mine or r["user_id"] == user["id"]]


@app.post("/api/needs")
def create_need(body: NeedInput, user=__import__("fastapi").Depends(current_user)):
    arrival = _iso_date(body.arrival_date, "Arrival date")
    start, end = _iso_date(body.available_from, "Available from"), _iso_date(body.available_until, "Available until")
    if end < start:
        raise HTTPException(422, "Available until must be on or after available from.")
    area = _general_area(body.area)
    time_from, time_until = _validate_local_times(body.time_from, body.time_until, "availability")
    id_ = str(uuid.uuid4())
    with connect() as db:
        db.execute("""INSERT INTO needs(id,user_id,item_name,category,quantity,arrival_date,available_from,available_until,area,time_from,time_until,has_vehicle,preferred_condition,essential_category,requires_delivery,status,is_demo,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?)""", (id_, user["id"], sanitize_public_text(body.item_name, 100), sanitize_public_text(body.category, 60), body.quantity, arrival, start, end, area, time_from, time_until, int(body.has_vehicle), sanitize_public_text(body.preferred_condition, 30), sanitize_public_text(body.essential_category, 60), int(body.requires_delivery), int(user["is_demo"]), now()))
        _mark_selected_plans_stale(db, need_ids=[id_])
        row = db.execute("SELECT * FROM needs WHERE id=?", (id_,)).fetchone()
    return _need_out(row)


@app.patch("/api/needs/{need_id}")
def edit_need(need_id: str, body: NeedInput, user=__import__("fastapi").Depends(current_user)):
    arrival = _iso_date(body.arrival_date, "Arrival date")
    available_from = _iso_date(body.available_from, "Available from")
    available_until = _iso_date(body.available_until, "Available until")
    if available_until < available_from:
        raise HTTPException(422, "Available until must be on or after available from.")
    area = _general_area(body.area)
    time_from, time_until = _validate_local_times(body.time_from, body.time_until, "availability")
    with connect() as db:
        row = db.execute("SELECT * FROM needs WHERE id=?", (need_id,)).fetchone()
        if not row or row["user_id"] != user["id"]:
            raise HTTPException(404, "Request not found.")
        db.execute("UPDATE needs SET item_name=?,category=?,quantity=?,arrival_date=?,available_from=?,available_until=?,area=?,time_from=?,time_until=?,has_vehicle=?,preferred_condition=?,essential_category=?,requires_delivery=? WHERE id=?", (sanitize_public_text(body.item_name, 100), sanitize_public_text(body.category, 60), body.quantity, arrival, available_from, available_until, area, time_from, time_until, int(body.has_vehicle), sanitize_public_text(body.preferred_condition, 30), sanitize_public_text(body.essential_category, 60), int(body.requires_delivery), need_id))
        _mark_selected_plans_stale(db, need_ids=[need_id])
        return _need_out(db.execute("SELECT * FROM needs WHERE id=?", (need_id,)).fetchone())


@app.get("/api/reservations")
def list_reservations(user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        rows = db.execute("""SELECT r.*,l.item_name,l.area,l.condition,l.user_id AS giver_id,
          l.available_from AS listing_from,l.pickup_deadline AS listing_until,l.pickup_windows AS listing_pickup_windows,
          l.time_from AS listing_time_from,l.time_until AS listing_time_until,g.display_name AS giver_name,
          u.display_name AS recipient_name FROM reservations r JOIN listings l ON l.id=r.listing_id
          JOIN users g ON g.id=l.user_id JOIN users u ON u.id=r.recipient_id
          WHERE r.recipient_id=? OR l.user_id=? ORDER BY r.created_at DESC""", (user["id"], user["id"])).fetchall()
        return [{**dict(r), "is_giver": r["giver_id"] == user["id"], "pickup_agreed": bool(r["pickup_agreed"]), "giver_confirmed": bool(r["giver_confirmed"]), "recipient_confirmed": bool(r["recipient_confirmed"])} for r in rows]


@app.post("/api/reservations")
def request_reservation(body: ReservationInput, user=__import__("fastapi").Depends(current_user)):
    rid = str(uuid.uuid4())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        listing = db.execute("SELECT * FROM listings WHERE id=?", (body.listing_id,)).fetchone()
        if not listing or listing["status"] != "available":
            raise HTTPException(409, "This listing is no longer available.")
        if listing["user_id"] == user["id"]:
            raise HTTPException(422, "You cannot request your own listing.")
        need = None
        if body.need_id:
            need = db.execute("SELECT * FROM needs WHERE id=? AND user_id=? AND status='open'", (body.need_id, user["id"])).fetchone()
            if not need:
                raise HTTPException(422, "Select one of your open requests.")
        else:
            need = {"quantity": body.quantity, "arrival_date": body.pickup_window[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", body.pickup_window) else "", "available_from": listing["available_from"], "available_until": listing["pickup_deadline"], "has_vehicle": body.transport_plan == "recipient vehicle", "preferred_condition": "", "essential_category": ""}
        need = dict(need)
        try:
            available = ensure_quantity_available(db, body.listing_id, body.quantity)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        compatibility = evaluate_match(dict(listing), dict(need), available)
        if compatibility["status"] == "incompatible":
            raise HTTPException(409, "; ".join(compatibility["issues"]))
        if listing["requires_vehicle"] and not need["has_vehicle"] and (not listing["can_deliver"] or body.transport_plan != "delivery requested"):
            raise HTTPException(409, "This item requires a vehicle and no delivery option is recorded.")
        if need.get("requires_delivery") and body.transport_plan != "delivery requested":
            raise HTTPException(422, "Request the giver's delivery agreement before continuing.")
        earliest = max(listing["available_from"], (need["available_from"] or need["arrival_date"]))
        latest = min(listing["pickup_deadline"], (need["available_until"] or need["arrival_date"]))
        _validate_pickup_window(body.pickup_window, earliest, latest, listing["time_from"], listing["time_until"], need.get("time_from", ""), need.get("time_until", ""))
        now_ = now()
        db.execute("INSERT INTO reservations(id,listing_id,need_id,recipient_id,quantity,status,transport_plan,pickup_window,is_demo,created_at,updated_at) VALUES(?,?,?,?,?,'requested',?,?,?, ?,?)", (rid, body.listing_id, body.need_id, user["id"], body.quantity, body.transport_plan, body.pickup_window, int(bool(listing["is_demo"]) and bool(user["is_demo"])), now_, now_))
        _mark_selected_plans_stale(db, listing_ids=[body.listing_id], need_ids=[body.need_id] if body.need_id else [])
        row = db.execute("SELECT * FROM reservations WHERE id=?", (rid,)).fetchone()
    return dict(row)


def _reservation_for(db, reservation_id: str, user: dict):
    row = db.execute("""SELECT r.*,l.user_id AS giver_id,l.quantity AS listing_quantity,
      l.available_from AS listing_from,l.pickup_deadline AS listing_until,
      l.time_from AS listing_time_from,l.time_until AS listing_time_until,
      n.available_from AS need_from,n.available_until AS need_until,n.arrival_date AS need_arrival,
      n.time_from AS need_time_from,n.time_until AS need_time_until
      FROM reservations r JOIN listings l ON l.id=r.listing_id
      LEFT JOIN needs n ON n.id=r.need_id WHERE r.id=?""", (reservation_id,)).fetchone()
    if not row or (row["recipient_id"] != user["id"] and row["giver_id"] != user["id"]):
        raise HTTPException(404, "Reservation not found.")
    return row


@app.post("/api/reservations/{reservation_id}/decision")
def reservation_decision(reservation_id: str, body: DecisionInput, user=__import__("fastapi").Depends(current_user)):
    if body.decision not in {"accept", "decline"}:
        raise HTTPException(422, "Decision must be accept or decline.")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _reservation_for(db, reservation_id, user)
        if row["giver_id"] != user["id"]:
            raise HTTPException(403, "Only the giver can accept or decline this request.")
        if row["status"] != "requested":
            raise HTTPException(409, "This request has already been handled.")
        if body.pickup_window:
            earliest = max(row["listing_from"], row["need_from"] or row["need_arrival"] or row["listing_from"])
            latest = min(row["listing_until"], row["need_until"] or row["need_arrival"] or row["listing_until"])
            _validate_pickup_window(body.pickup_window, earliest, latest, row["listing_time_from"], row["listing_time_until"], row["need_time_from"] or "", row["need_time_until"] or "")
        new_status = "reserved" if body.decision == "accept" else "declined"
        transport = "delivery agreed" if new_status == "reserved" and row["transport_plan"] == "delivery requested" else row["transport_plan"]
        db.execute("UPDATE reservations SET status=?,transport_plan=?,pickup_window=CASE WHEN ?<>'' THEN ? ELSE pickup_window END,pickup_agreed=?,updated_at=? WHERE id=?", (new_status, transport, body.pickup_window, body.pickup_window, int(new_status == "reserved" and bool(body.pickup_window)), now(), reservation_id))
        _mark_selected_plans_stale(db, listing_ids=[row["listing_id"]], need_ids=[row["need_id"]] if row["need_id"] else [])
        return dict(db.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone())


@app.post("/api/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: str, user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _reservation_for(db, reservation_id, user)
        if row["status"] not in {"requested", "reserved"}:
            raise HTTPException(409, "Only a requested or reserved handoff can be canceled.")
        db.execute("UPDATE reservations SET status='cancelled',updated_at=? WHERE id=?", (now(), reservation_id))
        _mark_selected_plans_stale(db, listing_ids=[row["listing_id"]], need_ids=[row["need_id"]] if row["need_id"] else [])
    return {"ok": True, "availability_restored": True}


@app.post("/api/reservations/{reservation_id}/confirm")
def confirm_handoff(reservation_id: str, body: ConfirmInput, user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _reservation_for(db, reservation_id, user)
        if row["status"] != "reserved":
            raise HTTPException(409, "Only a reserved handoff can be confirmed.")
        if user["id"] == row["giver_id"]:
            db.execute("UPDATE reservations SET giver_confirmed=1,updated_at=? WHERE id=?", (now(), reservation_id))
        else:
            db.execute("UPDATE reservations SET recipient_confirmed=1,updated_at=? WHERE id=?", (now(), reservation_id))
        fresh = db.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
        _mark_selected_plans_stale(db, listing_ids=[fresh["listing_id"]], need_ids=[fresh["need_id"]] if fresh["need_id"] else [])
        if fresh["giver_confirmed"] and fresh["recipient_confirmed"]:
            db.execute("UPDATE reservations SET status='completed',updated_at=? WHERE id=?", (now(), reservation_id))
            db.execute("UPDATE listings SET quantity=MAX(0,quantity-?) WHERE id=?", (fresh["quantity"], fresh["listing_id"]))
            if fresh["need_id"]:
                completed = db.execute("SELECT COALESCE(SUM(quantity),0) AS n FROM reservations WHERE need_id=? AND status='completed'", (fresh["need_id"],)).fetchone()["n"]
                need_quantity = db.execute("SELECT quantity FROM needs WHERE id=?", (fresh["need_id"],)).fetchone()
                if need_quantity and completed >= need_quantity["quantity"]:
                    db.execute("UPDATE needs SET status='fulfilled' WHERE id=?", (fresh["need_id"],))
        if fresh["giver_confirmed"] and fresh["recipient_confirmed"]:
            message = "Both people confirmed the completed physical exchange. These confirmations do not agree to a future pickup."
        elif user["id"] == row["giver_id"]:
            message = "Your confirmation that you have handed over the item is recorded; the recipient still needs to confirm the completed physical exchange."
        else:
            message = "Your confirmation that you have received the item is recorded; the giver still needs to confirm the completed physical exchange."
        return {"status": "completed" if fresh["giver_confirmed"] and fresh["recipient_confirmed"] else "reserved", "giver_confirmed": bool(fresh["giver_confirmed"]), "recipient_confirmed": bool(fresh["recipient_confirmed"]), "message": message}


@app.post("/api/plans")
def create_plan(body: PlanInput, user=__import__("fastapi").Depends(current_user)):
    if body.direction not in {"move_out", "move_in"}:
        raise HTTPException(422, "Direction must be move_out or move_in.")
    if body.direction == "move_out" and not body.listing_ids:
        raise HTTPException(422, "Select at least one of your listings.")
    if body.direction == "move_in" and not body.need_ids:
        raise HTTPException(422, "Select at least one of your requests.")
    try:
        validate_plan_input_size(body.listing_ids, body.need_ids, body.context)
    except ValueError as exc:
        raise HTTPException(413, str(exc))
    pid = str(uuid.uuid4())
    with connect() as db:
        since = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        count = db.execute("SELECT COUNT(*) AS n FROM plans WHERE user_id=? AND created_at>?", (user["id"], since)).fetchone()["n"]
        if count >= 5:
            raise HTTPException(429, "Planning is limited to five runs per account per day.")
        for listing_id in body.listing_ids:
            row = db.execute("SELECT user_id FROM listings WHERE id=?", (listing_id,)).fetchone()
            if not row or (body.direction == "move_out" and row["user_id"] != user["id"]):
                raise HTTPException(404, "A selected listing does not belong to your account.")
        for need_id in body.need_ids:
            row = db.execute("SELECT user_id FROM needs WHERE id=?", (need_id,)).fetchone()
            if not row or (body.direction == "move_in" and row["user_id"] != user["id"]):
                raise HTTPException(404, "A selected request does not belong to your account.")
        db.execute("INSERT INTO plans(id,user_id,direction,listing_ids_json,need_ids_json,result_json,status,created_at) VALUES(?,?,?,?,?,'{}','running',?)", (pid, user["id"], body.direction, json.dumps(body.listing_ids), json.dumps(body.need_ids), now()))
    if not os.environ.get("PORTKEY_API_KEY"):
        detail = "AI planning is unavailable until PORTKEY_API_KEY is configured. Add it to final project/.env or the .env in the directory immediately above this repository."
        with connect() as db:
            db.execute("UPDATE plans SET status='unavailable',result_json=? WHERE id=?", (json.dumps({"error": detail}), pid))
        raise HTTPException(503, detail)
    try:
        result = run_agent(pid, user["id"], body.direction, body.listing_ids, body.need_ids, body.context)
    except ValueError as exc:
        status, detail = "rejected", str(exc)
        with connect() as db:
            db.execute("UPDATE plans SET status=?,result_json=? WHERE id=?", (status, json.dumps({"error": detail}), pid))
        raise HTTPException(413, detail)
    except Exception as exc:
        # Do not expose provider exception text, which may contain request metadata.
        detail = f"The {MODEL} planning request failed. Check Portkey access and try again; no fallback model was used."
        with connect() as db:
            db.execute("UPDATE plans SET status='failed',result_json=? WHERE id=?", (json.dumps({"error": detail}), pid))
        raise HTTPException(502, detail)
    with connect() as db:
        db.execute("UPDATE plans SET status='completed',result_json=? WHERE id=?", (json.dumps(result, ensure_ascii=False), pid))
    return {"id": pid, "direction": body.direction, "status": "completed", "selected_listing_ids": body.listing_ids, "selected_need_ids": body.need_ids, **result}


@app.get("/api/plans")
def list_plans(user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        return [{"id": r["id"], "direction": r["direction"], "status": r["status"], "selected_listing_ids": json.loads(r["listing_ids_json"] or "[]"), "selected_need_ids": json.loads(r["need_ids_json"] or "[]"), "created_at": r["created_at"], "result": json.loads(r["result_json"])} for r in db.execute("SELECT * FROM plans WHERE user_id=? ORDER BY created_at DESC LIMIT 30", (user["id"],)).fetchall()]


@app.get("/api/resources")
def resources(user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        return [{**dict(r), "acceptance_verified": bool(r["source_verified_on"]), "accepted_items": r["accepted_items"].split("| ") if r["accepted_items"] else []} for r in db.execute("SELECT * FROM resources ORDER BY name").fetchall()]


@app.get("/api/usage")
def usage(user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        records = [dict(r) for r in db.execute("SELECT a.*,p.direction FROM ai_requests a JOIN plans p ON p.id=a.plan_id WHERE p.user_id=? ORDER BY a.created_at DESC LIMIT 100", (user["id"],)).fetchall()]
    for record in records:
        try:
            record["tool_names"] = json.loads(record.get("tool_names") or "[]")
        except (TypeError, json.JSONDecodeError):
            record["tool_names"] = []
    return {"model": MODEL, "requests": records, "pricing": None, "pricing_status": "Not verified from an authoritative current Portkey price source in this environment.", "cached_input_semantics": "Provider field is stored separately; whether it is included in input_tokens must be verified before costing.", "scenario_assumption_runs_per_user_month": 20, "costs": {"typical_run_usd": None, "one_user_month_usd": None, "100_users_usd": None, "10000_users_usd": None}}


@app.post("/api/demo/reset")
def reset_demo_data(user=__import__("fastapi").Depends(current_user)):
    with connect() as db:
        conflict = db.execute("""SELECT 1 FROM reservations r JOIN listings l ON l.id=r.listing_id
           WHERE l.is_demo=1 AND r.is_demo=0 LIMIT 1""").fetchone()
        if conflict:
            raise HTTPException(409, "A real account has a reservation record referencing demonstration data. The reset is paused to preserve that real record.")
        db.execute("BEGIN IMMEDIATE")
        reset_demo(db)
    return {"ok": True, "message": "Demonstration records restored. Real listings, requests, and reservations were kept."}
