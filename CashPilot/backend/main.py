import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import router as ingest_router


current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
dotenv_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path)


def _run_auto_seed():
    """Seed demo data in the background so app startup is not blocked."""
    print("\nCashPilot starting up with AUTO_SEED_ON_STARTUP=true...")
    try:
        from scripts.plaid_simulator import generate_simulator_data
        from scripts.seed_data import seed_database

        seed_database()
        generate_simulator_data()
        print("Fresh simulation data ready.\n")
    except Exception as exc:
        print(f"Auto-seed failed (non-fatal): {exc}\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Optionally seed fresh simulation data on startup."""
    auto_seed_enabled = os.getenv("AUTO_SEED_ON_STARTUP", "false").lower() == "true"

    if auto_seed_enabled:
        print("\nScheduling demo auto-seed in the background.")
        app.state.auto_seed_task = asyncio.create_task(asyncio.to_thread(_run_auto_seed))
    else:
        print("\nCashPilot starting up without auto-seeding.")
        print("Set AUTO_SEED_ON_STARTUP=true to reseed demo data on boot.\n")

    yield


app = FastAPI(
    title="CashPilot Backend API",
    description="AI-driven Financial Autopilot for SMBs - Perception Layer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.ai_router import router as ai_router
from api.dashboard_router import router as dash_router
from api.quant_router import router as quant_router
from api.simulation_router import router as sim_router

app.include_router(ingest_router, tags=["Ingestion"])
app.include_router(sim_router, tags=["Simulation Engine"])
app.include_router(dash_router, tags=["Dashboard & UI"])
app.include_router(quant_router, tags=["Quant Engine"])
app.include_router(ai_router, tags=["AI Orchestrator"])


@app.get("/")
def read_root():
    return {"message": "Welcome to the CashPilot Perception Layer API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
