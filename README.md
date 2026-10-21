# Andhra AI Planner

Andhra AI Planner is a web app that builds travel itineraries for you.

You tell it a city, your travel dates, and what you're into (temples, beaches,
museums, markets, and so on). It then puts together a plan for each day of the
trip — a list of real places to visit, in a sensible order, with a time for
each one.

**What makes it smart:**

- It uses AI (Google Gemini) to pick which places are worth visiting and to
  work out the best time of day for each one — temples in the morning, sunset
  viewpoints in the evening, and so on. The AI decides the plan; the app then
  does the plain math to check travel times and opening hours actually add up.
- It groups each day by location, so you're not driving back and forth across
  the city. One day = one area.
- It uses real place data and opening hours from Google, and shows each day's
  route on a map with numbered stops.

Once a plan is made, you can edit it freely: drag stops into a new order, move a
stop to another day, make a visit longer or shorter, swap a place for a similar
one nearby, lock the ones you don't want changed, or delete a stop. The map and
times update as you go.

You sign in with an email and password. Your trips are saved to your account
automatically, and you can reopen or delete them any time from "My trips."

---

## Tech stack

**Backend** — Python, FastAPI, SQLAlchemy 2.0, PostgreSQL + PostGIS
(GeoAlchemy2), Google Gemini (`google-genai`), Google Places API, OSRM for road
geometry, bcrypt + JWT (PyJWT) for auth.

**Frontend** — React 19, Vite, Tailwind CSS, Leaflet / react-leaflet,
`@dnd-kit` for drag & drop, axios.

---

## Setup

### Prerequisites
- Python 3.12
- Node.js 18+
- PostgreSQL with the PostGIS extension

### Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/trip_planner
PLACES_API_KEY=your_google_places_api_key
GEMINI_API_KEY=your_gemini_api_key
# Optional (a dev fallback is used if omitted — set a real value in production):
JWT_SECRET=change-me-to-a-long-random-string
JWT_EXPIRE_DAYS=7
```

Apply the schema (also runs automatically at startup) and launch the API:

```bash
python -m app.db.migrate      # idempotent: creates/updates tables
uvicorn app.main:app --reload
```

The API serves at `http://127.0.0.1:8000` (interactive docs at `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs at `http://localhost:5173`. To point it at a non-default
backend, set `VITE_API_BASE` (defaults to `http://127.0.0.1:8000`).

---

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/register` | Create an account, returns a JWT |
| POST | `/auth/login` | Sign in, returns a JWT |
| GET  | `/auth/me` | Current user (requires `Authorization: Bearer`) |
| GET  | `/keywords` | Interest categories for the picker |
| POST | `/trips/generate` | Build a new itinerary |
| GET  | `/trips` | List a user's trips |
| GET  | `/trips/{id}/itinerary` | Full itinerary |
| DELETE | `/trips/{id}` | Delete a trip (owner only) |
| GET  | `/trips/{id}/days/{n}/route` | Road geometry for a day |
| GET  | `/trips/{id}/days/{n}/suggestions` | Places that would fit the day |
| POST | `/trips/{id}/days/{n}/add` | Accept a suggestion |
| PATCH | `/trips/{id}/stops/reorder` | Reorder a day |
| PATCH | `/trips/{id}/stops/{sid}/duration` | Change a visit length |
| POST | `/trips/{id}/stops/{sid}/move` | Move a stop to another day |
| POST | `/trips/{id}/stops/{sid}/lock` | Toggle a lock |
| POST | `/trips/{id}/stops/{sid}/replace` | Swap in a similar place |
| POST | `/trips/{id}/stops/{sid}/preview` | Preview an edit (no writes) |
| POST | `/trips/{id}/recalculate` | Remove a stop and re-plan/backfill |

Protected routes expect an `Authorization: Bearer <token>` header; the frontend
attaches it automatically after sign-in.
