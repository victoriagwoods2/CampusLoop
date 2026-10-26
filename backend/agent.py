"""Bounded Portkey Responses API agent with real, deterministic tools."""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from core import evaluate_match, sanitize_public_text, validate_plan, validate_plan_input_size
from prompts import INSTRUCTIONS
from store import ROOT, connect, remaining_quantity

MODEL = "gpt-6-luna"
MAX_RESPONSES = 6
MAX_TOOL_CALLS = 8
MAX_TOOL_BYTES = 24_000
FINALIZE_AFTER_TOOL_CALLS = 4

TOOL_DEFS = [
    {"type": "function", "name": "retrieve_available_listings", "description": "Retrieve available real listings after deterministic date, vehicle, category, and quantity filtering; use for moving-in plans.", "strict": True, "parameters": {"type": "object", "properties": {"item_terms": {"type": "string", "maxLength": 100}, "need_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 10}}, "required": ["item_terms", "need_ids"], "additionalProperties": False}},
    {"type": "function", "name": "retrieve_selected_listings", "description": "Retrieve the selected real move-out listings and remaining quantities, including unavailable status for explanations.", "strict": True, "parameters": {"type": "object", "properties": {"listing_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 10}}, "required": ["listing_ids"], "additionalProperties": False}},
    {"type": "function", "name": "retrieve_move_in_needs", "description": "Retrieve actual open move-in needs; use for moving-out plans.", "strict": True, "parameters": {"type": "object", "properties": {"listing_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 10}}, "required": ["listing_ids"], "additionalProperties": False}},
    {"type": "function", "name": "retrieve_selected_needs", "description": "Retrieve the signed-in planner's selected actual move-in requests.", "strict": True, "parameters": {"type": "object", "properties": {"need_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 10}}, "required": ["need_ids"], "additionalProperties": False}},
    {"type": "function", "name": "check_match", "description": "Check real dates, quantity, status, condition, essential category, and transportation for one record pair.", "strict": True, "parameters": {"type": "object", "properties": {"listing_id": {"type": "string"}, "need_id": {"type": "string"}}, "required": ["listing_id", "need_id"], "additionalProperties": False}},
    {"type": "function", "name": "get_donation_resources", "description": "Retrieve source-linked local resource records and whether their acceptance information is verified.", "strict": True, "parameters": {"type": "object", "properties": {"item_category": {"type": "string", "maxLength": 80}}, "required": ["item_category"], "additionalProperties": False}},
    {"type": "function", "name": "validate_proposed_plan", "description": "Validate proposed IDs and quantities against the current database and deterministic feasibility rules.", "strict": True, "parameters": {"type": "object", "properties": {"matches": {"type": "array", "items": {"type": "object", "properties": {"listing_id": {"type": "string"}, "need_id": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1}, "why": {"type": "string", "maxLength": 240}}, "required": ["listing_id", "need_id", "quantity", "why"], "additionalProperties": False}, "maxItems": 20}}, "required": ["matches"], "additionalProperties": False}},
]


def _dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return {key: getattr(item, key) for key in ("type", "name", "arguments", "call_id", "id", "output") if hasattr(item, key)}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _record(row: Any) -> dict:
    data = dict(row)
    data["is_demo"] = bool(data.get("is_demo", 0))
    for field in ("item_name", "category", "description", "defects", "dimensions", "pickup_windows", "area"):
        if field in data:
            data[field] = sanitize_public_text(data[field], 240)
    return data


def _listings(item_terms: str = "", need_ids: list[str] | None = None) -> list[dict]:
    term = (item_terms or "").casefold().strip()
    term_tokens = set(re.findall(r"[a-z0-9]+", term))
    with connect() as db:
        selected_needs = []
        if need_ids:
            placeholders = ",".join("?" for _ in need_ids[:10])
            selected_needs = [_record(r) for r in db.execute(f"SELECT * FROM needs WHERE id IN ({placeholders}) AND status='open'", tuple(need_ids[:10])).fetchall()]
        rows = db.execute("SELECT * FROM listings WHERE status='available' ORDER BY created_at DESC LIMIT 40").fetchall()
        ranked = []
        for row in rows:
            data = _record(row)
            remaining = remaining_quantity(db, data["id"])
            if remaining < 1:
                continue
            searchable = (data["item_name"] + " " + data["category"] + " " + data["description"]).casefold()
            record_tokens = set(re.findall(r"[a-z0-9]+", searchable))
            if selected_needs:
                # For a selected request, deterministic compatibility is authoritative.
                # Model-provided keywords rank candidates; they must not hide a real compatible record.
                if not any(evaluate_match(data, need, remaining)["status"] != "incompatible" for need in selected_needs):
                    continue
            elif term and term not in searchable:
                continue
            data["remaining_quantity"] = remaining
            # descriptions are untrusted and intentionally truncated; no names, addresses, or contacts enter context.
            data["description"] = data["description"][:240]
            score = len(term_tokens & record_tokens)
            if term and term in searchable:
                score += len(term_tokens) + 1
            ranked.append((score, data))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [data for _, data in ranked[:20]]


def _selected_listings(listing_ids: list[str]) -> list[dict]:
    ids = list(dict.fromkeys(str(x) for x in listing_ids[:10]))
    if not ids:
        return []
    with connect() as db:
        rows = db.execute("SELECT * FROM listings WHERE id IN (%s)" % ",".join("?" for _ in ids), tuple(ids)).fetchall()
        out = []
        for row in rows:
            data = _record(row)
            data["remaining_quantity"] = remaining_quantity(db, data["id"])
            data["description"] = data["description"][:240]
            out.append(data)
        return out


def _needs(listing_ids: list[str]) -> list[dict]:
    ids = set(str(x) for x in listing_ids[:10])
    with connect() as db:
        rows = db.execute("SELECT * FROM needs WHERE status='open' ORDER BY created_at DESC LIMIT 40").fetchall()
        listing_categories = {}
        if ids:
            for row in db.execute("SELECT id,category FROM listings WHERE id IN (%s)" % ",".join("?" for _ in ids), tuple(ids)).fetchall():
                listing_categories[row["id"]] = row["category"]
        result = []
        for row in rows:
            data = _record(row)
            if ids and data.get("essential_category") and data["essential_category"] not in listing_categories.values():
                continue
            if ids:
                candidates = [dict(r) for r in db.execute("SELECT * FROM listings WHERE id IN (%s)" % ",".join("?" for _ in ids), tuple(ids)).fetchall()]
                if not any(evaluate_match(listing, data, remaining_quantity(db, listing["id"]))["status"] != "incompatible" for listing in candidates):
                    continue
            result.append(data)
        return result[:20]


def _selected_needs(need_ids: list[str]) -> list[dict]:
    ids = list(dict.fromkeys(str(x) for x in need_ids[:10]))
    if not ids:
        return []
    with connect() as db:
        rows = db.execute("SELECT * FROM needs WHERE id IN (%s) AND status='open'" % ",".join("?" for _ in ids), tuple(ids)).fetchall()
        return [_record(r) for r in rows]


def _resource_results(category: str) -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT * FROM resources ORDER BY name").fetchall()
        return [{
            "id": r["id"], "name": r["name"], "url": r["url"], "category": r["category"],
            "accepted_items": r["accepted_items"], "explicitly_excluded": r["explicitly_excluded"],
            "notes": r["notes"], "acceptance_verified": bool(r["source_verified_on"]),
        } for r in rows][:10]


def run_agent(plan_id: str, user_id: str, direction: str, listing_ids: list[str], need_ids: list[str], context: str = "") -> dict:
    """Run bounded tool loop; log each real API request, without prompt/output or secrets."""
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not configured. Add it to final project/.env or the .env one directory above the repository.")
    client = OpenAI(api_key=key, base_url="https://api.portkey.ai/v1", timeout=25.0, max_retries=0)
    with connect() as db:
        listing_rows = db.execute("SELECT * FROM listings WHERE id IN (%s)" % ",".join("?" for _ in listing_ids), tuple(listing_ids)).fetchall() if listing_ids else []
        need_rows = db.execute("SELECT * FROM needs WHERE id IN (%s)" % ",".join("?" for _ in need_ids), tuple(need_ids)).fetchall() if need_ids else []
    selected = [_record(r) for r in listing_rows]
    selected_needs = [_record(r) for r in need_rows]
    validate_plan_input_size(listing_ids, need_ids, context)
    request_text = {
        "direction": direction,
        "selected_listing_ids": listing_ids,
        "selected_need_ids": need_ids,
        "context": sanitize_public_text(context, 800),
        "purpose": "Build a small practical handoff plan; group by general neighborhood where possible without claiming distance or travel time.",
    }
    requests = 0
    tool_count = 0
    api_records: list[dict] = []
    input_items: Any = _json(request_text)
    last_response = None
    previous_response_id = None
    last_tool_results: dict[str, Any] = {}
    while requests < MAX_RESPONSES:
        requests += 1
        started = time.monotonic()
        request_tool_calls = 0
        try:
            request_options = {"input": input_items}
            if previous_response_id:
                request_options["previous_response_id"] = previous_response_id
            if tool_count >= FINALIZE_AFTER_TOOL_CALLS:
                # Require a final text response after the database checks, so the
                # model cannot spend the entire bounded run repeatedly calling tools.
                request_options["tool_choice"] = "none"
            response = client.responses.create(
                model=MODEL,
                instructions=INSTRUCTIONS,
                tools=TOOL_DEFS,
                max_output_tokens=700,
                **request_options,
            )
        except Exception:
            api_records.append({"model": MODEL, "input_tokens": None, "cached_input_tokens": None, "output_tokens": None, "latency_ms": round((time.monotonic()-started)*1000), "tool_calls": 0, "status": "error"})
            _store_usage(plan_id, api_records[-1])
            raise
        latency = round((time.monotonic() - started) * 1000)
        usage = getattr(response, "usage", None)
        details = getattr(usage, "input_tokens_details", None) if usage else None
        cached = getattr(details, "cached_tokens", None) if details else None
        rec = {
            "model": MODEL,
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "cached_input_tokens": cached,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
            "latency_ms": latency, "tool_calls": 0, "tool_names": [], "status": "success",
        }
        calls = [_dict(x) for x in getattr(response, "output", []) if _dict(x).get("type") == "function_call"]
        rec["tool_calls"] = len(calls)
        rec["tool_names"] = [str(call.get("name", "")) for call in calls]
        api_records.append(rec)
        _store_usage(plan_id, rec)
        last_response = response
        if not calls:
            break
        previous_response_id = getattr(response, "id", None)
        tool_outputs = []
        for call in calls:
            if tool_count >= MAX_TOOL_CALLS:
                raise RuntimeError("Planner reached its tool-call limit.")
            tool_count += 1
            request_tool_calls += 1
            name = call.get("name", "")
            args = json.loads(call.get("arguments") or "{}")
            if name == "retrieve_available_listings":
                result = _listings(str(args.get("item_terms", "")), [str(x) for x in args.get("need_ids", [])])
            elif name == "retrieve_selected_listings":
                result = _selected_listings([str(x) for x in args.get("listing_ids", [])])
            elif name == "retrieve_move_in_needs":
                result = _needs([str(x) for x in args.get("listing_ids", [])])
            elif name == "retrieve_selected_needs":
                result = _selected_needs([str(x) for x in args.get("need_ids", [])])
            elif name == "check_match":
                lid, nid = str(args.get("listing_id", "")), str(args.get("need_id", ""))
                ldata = next((x for x in selected if x["id"] == lid), None)
                ndata = next((x for x in selected_needs if x["id"] == nid), None)
                if not ldata:
                    with connect() as db:
                        row = db.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
                        ldata = _record(row) if row else None
                if not ndata:
                    with connect() as db:
                        row = db.execute("SELECT * FROM needs WHERE id=?", (nid,)).fetchone()
                        ndata = _record(row) if row else None
                if not ldata or not ndata:
                    result = {"status": "incompatible", "issues": ["Unknown listing or need ID."]}
                else:
                    with connect() as db:
                        result = evaluate_match(ldata, ndata, remaining_quantity(db, lid))
            elif name == "get_donation_resources":
                result = _resource_results(str(args.get("item_category", "")))
            elif name == "validate_proposed_plan":
                with connect() as db:
                    all_listings = {r["id"]: _record(r) for r in db.execute("SELECT * FROM listings").fetchall()}
                    all_needs = {r["id"]: _record(r) for r in db.execute("SELECT * FROM needs").fetchall()}
                    remaining = {id_: remaining_quantity(db, id_) for id_ in all_listings}
                result = validate_plan(args.get("matches", []), all_listings, all_needs, remaining)
                last_tool_results["validation"] = result
            else:
                result = {"error": "Unknown tool."}
            encoded = _json(result)
            if len(encoded.encode("utf-8")) > MAX_TOOL_BYTES:
                raise RuntimeError("Tool result exceeded the safe input-size limit.")
            if name == "check_match":
                last_tool_results[f"{args.get('listing_id')}:{args.get('need_id')}"] = result
            if name == "get_donation_resources":
                last_tool_results["resources"] = result
            tool_outputs.append({"type": "function_call_output", "call_id": call.get("call_id"), "output": encoded})
        input_items = tool_outputs
    else:
        raise RuntimeError("Planner reached its model-request limit without finishing.")
    output_text = getattr(last_response, "output_text", "") or ""
    parsed = _parse_output(output_text)
    with connect() as db:
        fresh_listings = {r["id"]: _record(r) for r in db.execute("SELECT * FROM listings").fetchall()}
        fresh_needs = {r["id"]: _record(r) for r in db.execute("SELECT * FROM needs").fetchall()}
        remaining = {id_: remaining_quantity(db, id_) for id_ in fresh_listings}
        resources = {r["id"]: dict(r) for r in db.execute("SELECT * FROM resources").fetchall()}
    valid = validate_plan(parsed.get("matches", []), fresh_listings, fresh_needs, remaining)
    valid["matches"] = [m for m in valid["matches"] if m["listing_id"] in listing_ids or direction == "move_in"]
    giver_counts: dict[str, int] = {}
    for match in valid["matches"]:
        owner_id = str(fresh_listings[match["listing_id"]].get("user_id", ""))
        giver_counts[owner_id] = giver_counts.get(owner_id, 0) + 1
    for match in valid["matches"]:
        listing = fresh_listings[match["listing_id"]]
        need = fresh_needs[match["need_id"]]
        match["listing"] = {"item_name": listing["item_name"], "category": listing["category"], "area": listing["area"], "is_demo": bool(listing["is_demo"])}
        match["need"] = {"item_name": need["item_name"], "area": need["area"], "is_demo": bool(need["is_demo"])}
        match["same_giver_group_size"] = giver_counts.get(str(listing.get("user_id", "")), 1)
    clarifications = []
    for proposal in valid["rejected"]:
        if proposal.get("status") == "clarify" and proposal["listing_id"] in fresh_listings and proposal["need_id"] in fresh_needs:
            clarifications.append({"listing_id": proposal["listing_id"], "need_id": proposal["need_id"], "issue": proposal["reason"], "next_action": "Confirm this detail with the other person before requesting."})
    checked_resources = []
    for candidate in parsed.get("resources", [])[:10]:
        resource = resources.get(str(candidate.get("resource_id", "")))
        if resource:
            checked_resources.append({"resource_id": resource["id"], "name": resource["name"], "url": resource["url"], "item": str(candidate.get("item", ""))[:100], "why": str(candidate.get("why", ""))[:180], "acceptance_verified": bool(resource["source_verified_on"]), "next_action": "Open the official source and confirm current acceptance rules before traveling."})
    selected_ids = listing_ids if direction == "move_out" else [m["listing_id"] for m in valid["matches"]]
    matched_ids = {m["listing_id"] for m in valid["matches"]}
    unmatched = []
    if direction == "move_out":
        for lid in selected_ids:
            row = fresh_listings.get(lid)
            if row and lid not in matched_ids:
                unmatched.append({"listing_id": lid, "item_name": row["item_name"], "reason": "No validated feasible student match was returned. Check date and transport details, or review the source-linked options below."})
    else:
        matched_need = {m["need_id"] for m in valid["matches"]}
        for nid in need_ids:
            row = fresh_needs.get(nid)
            if row and nid not in matched_need:
                unmatched.append({"need_id": nid, "item_name": row["item_name"], "reason": "No validated feasible available listing was found for this request."})
    return {
        "matches": valid["matches"], "possible_matches": clarifications, "rejected_proposals": valid["rejected"], "unmatched": unmatched,
        "resources": checked_resources,
        "missing_info": [str(x)[:200] for x in parsed.get("missing_info", [])[:8]],
        "usage": {"model": MODEL, "requests": api_records, "total_input_tokens": _sum_field(api_records, "input_tokens"), "total_cached_input_tokens": _sum_field(api_records, "cached_input_tokens"), "total_output_tokens": _sum_field(api_records, "output_tokens"), "cost_usd": None, "pricing_status": "Pricing not verified for this Portkey account/model."},
        "action_summary": "Recommendations are proposals only. Request items through the reservation workflow; both people must confirm the handoff.",
    }


def _sum_field(records: list[dict], field: str) -> int | None:
    values = [r[field] for r in records if isinstance(r.get(field), int)]
    return sum(values) if values and len(values) == sum(r.get(field) is not None for r in records) else None


def _parse_output(text: str) -> dict:
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        result = json.loads(text[start:end])
        if not isinstance(result, dict):
            raise ValueError("Expected an object")
        for key in ("matches", "unmatched", "resources", "missing_info"):
            if not isinstance(result.get(key, []), list):
                result[key] = []
        return result
    except (ValueError, json.JSONDecodeError):
        return {"matches": [], "unmatched": [], "resources": [], "missing_info": ["The model did not return a valid structured plan. Review listings directly."]}


def _store_usage(plan_id: str, record: dict, update: bool = False) -> None:
    with connect() as db:
        if update:
            row = db.execute("SELECT id FROM ai_requests WHERE plan_id=? ORDER BY rowid DESC LIMIT 1", (plan_id,)).fetchone()
            if row:
                db.execute("UPDATE ai_requests SET tool_calls=?,tool_names=? WHERE id=?", (record.get("tool_calls", 0), _json(record.get("tool_names", [])), row["id"]))
                return
        db.execute("INSERT INTO ai_requests(id,plan_id,model,input_tokens,cached_input_tokens,output_tokens,latency_ms,tool_calls,tool_names,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
            str(uuid.uuid4()), plan_id, record["model"], record.get("input_tokens"), record.get("cached_input_tokens"), record.get("output_tokens"), record.get("latency_ms"), record.get("tool_calls", 0), _json(record.get("tool_names", [])), record["status"], datetime.now(timezone.utc).isoformat()))
    out = ROOT / "output" / "usage.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(_json({**record, "plan_id": plan_id, "recorded_at": datetime.now(timezone.utc).isoformat()}) + "\n")
