"""Pure matching and validation rules shared by the API, planner, and tests."""
from datetime import date
import re
from typing import Any


def _day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def sanitize_public_text(value: Any, limit: int = 600) -> str:
    """Bound user text and strip common contact/address forms before public/model use."""
    text = str(value or "")[:limit]
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[contact removed]", text, flags=re.I)
    text = re.sub(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\w)", "[contact removed]", text)
    text = re.sub(r"\b\d{1,5}\s+[A-Za-z0-9.' -]{1,40}\b(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Court|Ct\.?)\b", "[address removed]", text, flags=re.I)
    return text


def validate_plan_input_size(listing_ids: list[str], need_ids: list[str], context: str = "") -> None:
    if len(listing_ids) + len(need_ids) > 20:
        raise ValueError("Select no more than 20 listings and needs combined.")
    if len(str(context).encode("utf-8")) > 3200:
        raise ValueError("Planning context is too large.")


def evaluate_match(listing: dict, need: dict, remaining_quantity: int | None = None) -> dict:
    """Return feasible / clarify / incompatible based on actual constraints."""
    issues: list[str] = []
    hard: list[str] = []
    quantity = int(listing.get("quantity", 0) if remaining_quantity is None else remaining_quantity)
    requested = int(need.get("quantity", 1))
    status = listing.get("status", "available")
    if status not in {"available", "requested"} or quantity <= 0:
        hard.append("This listing is no longer available.")
    if requested <= 0 or quantity < requested:
        hard.append("There is not enough unreserved quantity.")

    start = _day(listing.get("available_from"))
    end = _day(listing.get("pickup_deadline"))
    need_start = _day(need.get("available_from") or need.get("arrival_date"))
    need_end = _day(need.get("available_until") or need.get("availability_end") or need.get("arrival_date"))
    if not (start and end and need_start and need_end):
        issues.append("A pickup availability date is missing; confirm timing.")
    elif max(start, need_start) > min(end, need_end):
        hard.append("The pickup dates do not overlap; no storage arrangement is recorded.")

    if need.get("essential_category") and need.get("category"):
        if str(need["essential_category"]).casefold() != str(listing.get("category", "")).casefold():
            hard.append("The listing does not meet the requested essential category.")
    if need.get("preferred_condition"):
        rank = {"poor": 0, "fair": 1, "good": 2, "like new": 3, "new": 4}
        wanted = rank.get(str(need["preferred_condition"]).casefold())
        actual = rank.get(str(listing.get("condition", "")).casefold())
        if wanted is not None and actual is not None and actual < wanted:
            hard.append("The condition is below the recipient's stated minimum.")

    if listing.get("requires_vehicle") and not need.get("has_vehicle"):
        if listing.get("can_deliver"):
            issues.append("The giver offers delivery, but delivery must be explicitly agreed.")
        else:
            hard.append("This item requires a vehicle and no confirmed transport is available.")
    if need.get("requires_delivery"):
        if not listing.get("can_deliver"):
            hard.append("The recipient needs delivery, but the listing has no delivery option.")
        else:
            issues.append("Delivery is possible but still needs the giver's explicit agreement.")
    if not start or not end:
        issues.append("The listing has incomplete pickup availability.")

    giver_from, giver_until = listing.get("time_from", ""), listing.get("time_until", "")
    recipient_from, recipient_until = need.get("time_from", ""), need.get("time_until", "")
    if bool(giver_from) != bool(giver_until) or bool(recipient_from) != bool(recipient_until):
        issues.append("A pickup time range is incomplete; confirm the available hours.")
    elif giver_from and recipient_from and max(giver_from, recipient_from) > min(giver_until, recipient_until):
        hard.append("The listed local pickup time ranges do not overlap.")

    if hard:
        return {"status": "incompatible", "issues": hard + issues}
    if issues:
        return {"status": "clarify", "issues": issues}
    return {"status": "feasible", "issues": []}


def validate_plan(matches: list[dict], listing_by_id: dict[str, dict], need_by_id: dict[str, dict], remaining_by_id: dict[str, int]) -> dict:
    """Accept only real records and deterministic feasible matches."""
    accepted: list[dict] = []
    rejected: list[dict] = []
    allocated: dict[str, int] = {}
    need_allocated: dict[str, int] = {}
    for proposed in matches[:20]:
        lid, nid = str(proposed.get("listing_id", "")), str(proposed.get("need_id", ""))
        listing, need = listing_by_id.get(lid), need_by_id.get(nid)
        if listing is None or need is None:
            rejected.append({"listing_id": lid, "need_id": nid, "reason": "Unknown record ID."})
            continue
        need_free = int(need.get("quantity", 1)) - need_allocated.get(nid, 0)
        qty = min(int(proposed.get("quantity", 1)), need_free)
        free = int(remaining_by_id.get(lid, 0)) - allocated.get(lid, 0)
        check_need = {**need, "quantity": qty}
        check = evaluate_match(listing, check_need, free)
        if qty < 1 or check["status"] != "feasible":
            rejected.append({"listing_id": lid, "need_id": nid, "status": check["status"], "reason": "; ".join(check["issues"]) or "Need quantity is already allocated or the proposed quantity is invalid."})
            continue
        allocated[lid] = allocated.get(lid, 0) + qty
        need_allocated[nid] = need_allocated.get(nid, 0) + qty
        accepted.append({
            "listing_id": lid, "need_id": nid, "quantity": qty,
            "why": str(proposed.get("why", "Dates, quantity, and transportation meet the recorded requirements."))[:240],
            "next_action": "Review the details, then request the item if they work for you.",
            "issues": [],
        })
    return {"matches": accepted, "rejected": rejected}
