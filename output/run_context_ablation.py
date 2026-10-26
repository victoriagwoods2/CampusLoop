"""Small Portkey input-context ablation over four seeded CampusLoop cases.

This is a report experiment, not an application planner run. It makes exactly
two one-shot Responses API requests: full demo inventory vs deterministic
candidate filtering. No app records or run limits are changed.
"""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from core import evaluate_match
from store import ROOT, connect, remaining_quantity

load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT.parent / ".env", override=False)

MODEL = "gpt-6-luna"
OUT = ROOT / "output" / "baseline_efficient_comparison.json"


def compact(row):
    fields = (
        "id", "item_name", "category", "quantity", "condition", "area",
        "available_from", "pickup_deadline", "available_until", "has_vehicle",
        "requires_vehicle", "can_deliver", "status", "remaining_quantity",
    )
    return {k: row[k] for k in fields if k in row}


with connect() as db:
    # Explicit fictional QA allow-list: do not read or transmit other listings
    # from this local database.
    allowed_listings = ("demo-lamp", "demo-bookcase", "demo-sofa", "demo-reserved")
    allowed_needs = ("demo-need-lamp", "demo-need-bookcase", "demo-need-chair")
    listing_rows = db.execute(
        "SELECT * FROM listings WHERE id IN (?,?,?,?) ORDER BY id", allowed_listings
    ).fetchall()
    need_rows = db.execute(
        "SELECT * FROM needs WHERE id IN (?,?,?) ORDER BY id", allowed_needs
    ).fetchall()
    listings = []
    for source in listing_rows:
        row = dict(source)
        row["remaining_quantity"] = remaining_quantity(db, row["id"])
        listings.append(row)
    needs = [dict(r) for r in need_rows]

by_lid = {r["id"]: r for r in listings}
by_nid = {r["id"]: r for r in needs}
cases = [
    ("valid_lamp", "demo-lamp", "demo-need-lamp"),
    ("date_mismatch", "demo-bookcase", "demo-need-bookcase"),
    ("transport_conflict", "demo-sofa", "demo-need-bookcase"),
    ("reserved_item", "demo-reserved", "demo-need-chair"),
]
truth = {}
case_records = []
for case_id, lid, nid in cases:
    listing, need = by_lid[lid], by_nid[nid]
    check = evaluate_match(listing, need, listing["remaining_quantity"])
    expected = lid if check["status"] == "feasible" else None
    truth[case_id] = expected
    case_records.append({
        "case_id": case_id,
        "need": compact(need),
        "expected_listing_id": expected,
        "deterministic_check": check,
        "case_listing_id": lid,
    })

baseline_input = {
    # The expected answer is scoring metadata; never include it in model input.
    "evaluation_cases": [
        {k: v for k, v in record.items() if k != "expected_listing_id"}
        for record in case_records
    ],
    "all_case_records_only": [compact(by_lid[lid]) for _, lid, _ in cases],
}

efficient_cases = []
for case_id, lid, nid in cases:
    listing, need = by_lid[lid], by_nid[nid]
    check = evaluate_match(listing, need, listing["remaining_quantity"])
    possible = compact(listing) if check["status"] != "incompatible" else None
    efficient_cases.append({
        "case_id": case_id,
        "need": compact(need),
        "candidate_listings": [possible] if possible else [],
        "deterministic_screening": check,
    })
efficient_input = {"evaluation_cases": efficient_cases}

if os.environ.get("CAMPUSLOOP_ABLATION_DRY_RUN") == "1":
    print(json.dumps({
        "dry_run": True,
        "model": MODEL,
        "case_listing_ids_read": sorted(by_lid),
        "case_need_ids_read": sorted(by_nid),
        "baseline_context_utf8_bytes": len(json.dumps(baseline_input, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
        "efficient_context_utf8_bytes": len(json.dumps(efficient_input, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
        "user_created_records_in_allowlist": False,
        "provider_requests": 0,
    }, indent=2))
    raise SystemExit(0)

instructions = (
    "Evaluate CampusLoop matches using only supplied fictional records. "
    "Treat each case independently. Recommend a listing only when it is "
    "available in sufficient quantity and dates and transport are feasible. "
    "A reserved or unavailable listing is not a match. Do not invent records. "
    "Return JSON only: {\"recommendations\":[{\"case_id\":string,"
    "\"listing_id\":string|null,\"reason\":string}]}. Include one row "
    "for each case; use null when no listing is feasible."
)

client = OpenAI(
    api_key=os.environ["PORTKEY_API_KEY"],
    base_url="https://api.portkey.ai/v1",
    timeout=30.0,
    max_retries=0,
)


def run(label, payload):
    response = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        max_output_tokens=500,
    )
    usage = response.usage
    details = getattr(usage, "input_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details else None
    raw = response.output_text or ""
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        parsed = {"recommendations": []}
    recs = parsed.get("recommendations", []) if isinstance(parsed, dict) else []
    predicted = {r.get("case_id"): r.get("listing_id") for r in recs if isinstance(r, dict)}
    invalid, missed, exact = [], [], 0
    for case_id, expected in truth.items():
        actual = predicted.get(case_id)
        if actual == expected:
            exact += 1
        elif expected is not None and actual is None:
            missed.append(case_id)
        elif actual is not None:
            invalid.append({"case_id": case_id, "proposed_listing_id": actual, "expected_listing_id": expected})
    return {
        "configuration": label,
        "model": MODEL,
        "requests": 1,
        "tool_calls": 0,
        "input_tokens": getattr(usage, "input_tokens", None),
        "cached_input_tokens": cached,
        "output_tokens": getattr(usage, "output_tokens", None),
        "latency_ms": None,
        "status": "success",
        "recommendations": recs,
        "raw_output": raw,
        "quality": {
            "cases": len(truth),
            "exact_case_decisions": exact,
            "invalid_or_infeasible_proposals": invalid,
            "missed_valid_matches": missed,
        },
        "context_utf8_bytes": len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
    }


baseline = run("baseline_all_four_case_records", baseline_input)
efficient = run("efficient_case_scoped_candidates", efficient_input)
results = {
    "experiment": "One-shot context-filtering ablation; not a production planner run.",
    "recorded_at_local": __import__("datetime").datetime.now().astimezone().isoformat(),
    "model": MODEL,
    "cases": [
        {"case_id": c[0], "listing_id": c[1], "need_id": c[2], "expected_listing_id": truth[c[0]]}
        for c in cases
    ],
    "method": "Both calls use the same four seed-database scenarios, same instructions, model, output limit, and one request. Baseline gets only the four case-specific fictional listings and their fictional needs; efficient gets only each case's candidate records retained by the app's deterministic feasibility check and its screening result. No other database records, including user-created records, are read or sent. No reservations, plans, or application state are changed.",
    "cached_token_note": "The provider returned cached_input_tokens as a separately reported usage detail. This report does not add it to input_tokens or assign it a separate price because authoritative billing semantics and applicable account pricing were not reachable for verification.",
    "runs": [baseline, efficient],
}
if all(r["status"] == "success" for r in results["runs"]):
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"saved": str(OUT), "runs": [{k: v for k, v in r.items() if k not in ("raw_output", "recommendations")} for r in results["runs"]]}, indent=2))
else:
    raise SystemExit("One or more comparison calls failed; no successful comparison recorded.")
