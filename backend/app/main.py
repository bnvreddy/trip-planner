from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, places, trips
from app.db.migrate import ensure_schema


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Keep the live schema in step with the models; a stale column used to turn
    # into a 500 on the first trip generation.
    try:
        ensure_schema()
        print("Schema check: up to date")
    except Exception as exc:  # noqa: BLE001 - never block startup on this
        print(f"Schema check FAILED: {type(exc).__name__}: {exc}")
    yield


app = FastAPI(title="AI-Based Smart Trip Planner API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, tags=["Auth"])
app.include_router(places.router, tags=["Places"])
app.include_router(trips.router, tags=["Trips"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Modular Dynamic Trip Planner API!"}