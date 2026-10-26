# CampusLoop

CampusLoop is a local prototype for item-level listings and move-in requests. It checks whether a proposed match fits the records’ dates, quantities, condition, availability, and transport details. It is an independent class project, not a Yale service or endorsement. Demo accounts, listings, requests, and handoffs are fictional.

Public repository: <https://github.com/victoriagwoods2/CampusLoop>

## Requirements

- Python 3.11 or newer (developed and verified with Python 3.13)
- Node.js 20.19+ or 22.12+ (Vite 8 requirement)
- npm 9 or newer (the lockfile uses npm's version 3 format)
- A modern browser
- A Portkey API key for live AI planning; listing, request, and handoff workflows work without one

## Install

Clone the public repository, then run the setup commands from its root:

```bash
git clone https://github.com/victoriagwoods2/CampusLoop.git
cd CampusLoop
```

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

The example selects Python 3.13; if you use another supported Python 3.11+ release, substitute its executable name.

For a repository-local configuration, run `cp .env.example .env` from the repository root and set `PORTKEY_API_KEY` to your own key in `.env`. The backend also reads `.env` from the directory immediately above the repository, which is useful when cloning inside a workspace that already holds the key. Existing process environment values take precedence over both files. Never commit or share `.env`.

The planner sends requests through Portkey using **`gpt-6-luna`**. It has no canned-result or model fallback. Without a key, the rest of the app remains usable and planning reports that the provider is unavailable.

## Demo data and accounts

On first backend startup, CampusLoop creates `data/campusloop.sqlite3` and initializes the fictional demo accounts, listings, needs, reservation, and resource entries. No separate seed command is needed. The in-app **Reset demo data** action restores demo-owned records and preserves user-created records.

| Account | Email | Password |
| --- | --- | --- |
| Demo giver | `outgoing@campusloop.demo` | `demo-outgoing` |
| Demo recipient | `incoming@campusloop.demo` | `demo-incoming` |

These are public demonstration credentials, not real student accounts. The local SQLite database and session state are intentionally excluded from version control.

## Run the app

Start the backend in one terminal from the repository root:

```bash
cd backend
../.venv/bin/uvicorn app:app --reload --host 127.0.0.1 --port 8001
```

Start the frontend in a second terminal from the repository root:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5173
```

Open <http://127.0.0.1:5173>. The backend API is at <http://127.0.0.1:8001>; its health endpoint is `/api/health`. The development frontend uses port 5173 and the backend uses port 8001.

## Example workflow

1. Sign in as the demo giver. On **Moving Out**, choose **Add an item** and enter an item, quantity, neighborhood, availability dates, and any transport details.
2. Switch to the demo recipient. On **Moving In**, choose **Add a request** with overlapping dates and the needed item category.
3. Generate an AI plan for that request. Review the proposed match and its compatibility explanation; the planner reads database records and validates its proposal. It does not create a reservation.
4. On **Find Items**, the recipient requests the item. Switch to the giver and accept the request. The giver may agree to the recipient’s proposed pickup date and time during acceptance; the listing availability window alone is not an appointment.
5. Once the physical exchange has happened, confirm it from both accounts using the role-specific handoff action. The demo workflow updates reservation status and remaining quantity; it does not represent a real pickup.

## Development checks

The repository includes deterministic safety checks and the existing test suite. To run them locally:

```bash
.venv/bin/python tests/run_safety.py
.venv/bin/python -m pytest
cd frontend && npm run build
```

`output/` contains selected run records, check results, and screenshots supporting the report. `output/build_report.py` generates the self-contained `report.html`; `slides.html` is self-contained and includes its presentation assets. Independent student testing was not conducted. See `USABILITY_TEST.md` for the proposed task, which has not been run with an independent participant.

The default local database is `data/campusloop.sqlite3`. Keep your local database backed up. Do not delete it to reset the demo; use the in-app reset, which only restores demo-owned rows.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `GET/POST /api/listings`, `PATCH /api/listings/{id}`, `POST /api/listings/{id}/withdraw`
- `GET/POST /api/needs`, `PATCH /api/needs/{id}`
- `POST /api/plans`, `GET /api/plans`, `GET /api/usage`
- `POST /api/reservations`, `POST /api/reservations/{id}/decision`, `/cancel`, `/confirm`
- `GET /api/resources`, `POST /api/demo/reset`, `GET /api/health`

For a different browser origin, set `FRONTEND_ORIGIN` in the environment. The default local CORS configuration permits the Vite frontend at `http://localhost:5173` and `http://127.0.0.1:5173`.
