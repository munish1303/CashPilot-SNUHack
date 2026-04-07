# CashPilot

CashPilot is an AI-driven financial autopilot for small and medium businesses (SMBs). It monitors cash flow in real time, predicts runway, optimizes payment strategies using linear programming, and autonomously drafts vendor communications — all with a human-in-the-loop approval model.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture Overview](#architecture-overview)
3. [Project Structure](#project-structure)
4. [Database Schema](#database-schema)
5. [Prerequisites](#prerequisites)
6. [Environment Variables](#environment-variables)
7. [Installation](#installation)
8. [Running the App](#running-the-app)
9. [Seeding Demo Data](#seeding-demo-data)
10. [API Reference](#api-reference)
11. [Key Concepts](#key-concepts)
12. [Demo Mode](#demo-mode)

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16.2.1 | React framework with App Router |
| React | 19.2.4 | UI library |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 4 | Utility-first styling |
| Recharts | 3.x | Cash flow charts and sparklines |
| Framer Motion | 12.x | UI animations |
| Lucide React | 1.x | Icon library |

### Backend
| Technology | Purpose |
|---|---|
| FastAPI | Python REST API framework |
| Uvicorn | ASGI server |
| PostgreSQL | Primary database |
| psycopg2 | PostgreSQL driver |
| Google Gemini 2.5 Flash | AI text generation and Vision OCR |
| RapidFuzz | Fuzzy string matching for receipt reconciliation |
| python-dotenv | Environment variable management |
| python-multipart | File upload handling |
| Twilio | WhatsApp escalation alerts |

---

## Architecture Overview

CashPilot is built in four streams that form a pipeline from raw data to actionable decisions:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   STREAM 1   │     │   STREAM 2   │     │   STREAM 3   │     │   STREAM 4   │
│              │     │              │     │              │     │              │
│   Data       │────▶│ Mathematical │────▶│ AI           │────▶│  Frontend    │
│   Ingestion  │     │ Engine       │     │ Orchestrator │     │  UI          │
│              │     │              │     │              │     │              │
│ • Receipt OCR│     │ • Runway D2Z │     │ • Email      │     │ • Dashboard  │
│ • PDF Parser │     │ • LP Solver  │     │   Drafting   │     │ • Inbox      │
│ • Reconcile  │     │ • Monte Carlo│     │ • Zombie     │     │ • Analytics  │
│              │     │ • Phantom    │     │   Detector   │     │ • Ingestion  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Stream 1 — Data Ingestion
Handles all incoming financial data. Receipts and invoices are uploaded as images or PDFs, parsed by Gemini Vision OCR, and reconciled against existing obligations using fuzzy matching (RapidFuzz). If a match is found, the obligation is marked paid. If not, a new pending obligation is created.

### Stream 2 — Mathematical Engine
Pure deterministic math with zero AI involvement:
- **Runway Engine**: Simulates a day-by-day ledger over 30 days to calculate "Days to Zero" (D2Z) — the exact date the company runs out of cash.
- **Phantom Balance**: Calculates truly usable cash by ring-fencing locked obligations (taxes, payroll) from the gross bank balance.
- **LP Optimizer**: Uses linear programming to determine the optimal payment deferral strategy — which vendors to pay now, which to delay, and by how much — while respecting tier constraints.
- **Monte Carlo**: Runs 10,000 simulations with randomized payment delays, invoice latency variance, and a 5% receivable default rate to produce a probabilistic survival score.

### Stream 3 — AI Orchestrator
Translates mathematical decisions into human communication. The AI has zero financial authority — it cannot change amounts, dates, or priorities. It only drafts emails and logs them for user approval.
- **Action Generator**: Drafts payment delay requests and receivable acceleration offers using Gemini, with tone adapted to vendor tier and goodwill score.
- **Zombie Detector**: Identifies recurring subscriptions that are unused and generates cancellation drafts.
- **Negotiation Agent**: Multi-agent swarm for back-and-forth vendor negotiation.
- **Inventory Liquidator**: Generates Shopify flash sale and Stripe invoice factoring payloads for emergency cash injection.
- **Board Report**: One-click AI-generated investor update combining runway data and recent actions.

### Stream 4 — Frontend UI
Next.js dashboard with four main views:
- **Dashboard**: Executive summary with cash vitals, 14-day runway sparkline, LP optimization strategy, and Monte Carlo survival ring.
- **Action Inbox**: All AI-generated drafts pending user approval, with full Chain-of-Thought reasoning visible.
- **Analytics**: 30-day cash flow projection, vendor goodwill radar chart, and detailed Monte Carlo percentile breakdown.
- **Ingestion**: Receipt/PDF upload interface and recent transaction history.

---

## Project Structure

```
cashpilot/
├── app/                          # Next.js frontend (App Router)
│   ├── page.tsx                  # Dashboard page
│   ├── layout.tsx                # Root layout with Sidebar
│   ├── globals.css               # Global styles
│   ├── mockState.ts              # Demo fallback data
│   ├── analytics/page.tsx        # Analytics page
│   ├── inbox/page.tsx            # Action inbox page
│   ├── ingestion/page.tsx        # Receipt upload page
│   ├── components/
│   │   ├── Sidebar.tsx           # Navigation + simulation slider
│   │   ├── ActionInbox.tsx       # Action list with approval UI
│   │   ├── RadarChart.tsx        # Vendor goodwill radar
│   │   ├── RadarChartClient.tsx  # Client-side radar wrapper
│   │   └── SimulationSlider.tsx  # Date advancement control
│   └── context/
│       └── SimulationContext.tsx # Global simulation state
│
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── api/
│   │   ├── router.py             # Ingestion routes
│   │   ├── dashboard_router.py   # Dashboard, inbox, analytics routes
│   │   ├── quant_router.py       # Quant engine routes
│   │   ├── simulation_router.py  # Simulation advance route
│   │   └── ai_router.py          # AI orchestrator routes
│   ├── core/
│   │   └── db.py                 # PostgreSQL connection manager
│   ├── quant/
│   │   ├── runway_engine.py      # Days-to-Zero calculation
│   │   ├── phantom_balance.py    # Usable cash calculation
│   │   ├── optimizer.py          # LP payment optimizer
│   │   └── monte_carlo.py        # Monte Carlo simulation
│   ├── ai/
│   │   ├── action_generator.py   # Email drafting with Gemini
│   │   ├── zombie_detector.py    # Subscription analysis
│   │   ├── negotiation_agent.py  # Multi-agent negotiation
│   │   ├── inventory_liquidator.py # Emergency cash options
│   │   ├── board_report.py       # Investor update generator
│   │   └── tools.py              # LangChain tool definitions
│   ├── services/
│   │   ├── ingestion_pipeline.py # OCR parsing + reconciliation
│   │   ├── pdf_processor.py      # PDF contract extraction
│   │   ├── whatsapp_escalation.py# Defcon 1 WhatsApp alerts
│   │   └── demo_mode.py          # Mock data fallbacks
│   └── scripts/
│       ├── seed_data.py          # Populate demo database
│       ├── plaid_simulator.py    # Generate test transactions
│       ├── goodwill_scorer.py    # Update vendor goodwill scores
│       ├── run_all.py            # Run all setup scripts
│       ├── test_backend_api.py   # API endpoint tests
│       └── test_full_flow.py     # End-to-end flow tests
│
├── schema.sql                    # PostgreSQL schema
├── shared_contracts.json         # Shared data contracts (frontend ↔ backend)
├── package.json                  # Frontend dependencies
└── .env                          # Environment variables (create this)
```

---

## Database Schema

Five tables power the entire system:

```sql
-- The company being monitored
companies (id, name, plaid_current_balance, current_simulated_date, last_synced_at)

-- Vendors and clients with tier classification
entities (id, company_id, name, entity_type, ontology_tier, goodwill_score, late_fee_rate, avg_latency_days)

-- Historical cleared transactions
transactions (id, entity_id, amount, cleared_date, source)

-- Pending payables (negative) and receivables (positive)
obligations (id, entity_id, amount, due_date, status, is_locked)

-- AI-generated actions awaiting user approval
action_logs (id, company_id, action_type, message, is_resolved, status, chain_of_thought, execution_type, execution_payload, agent_thread_id)
```

### Ontology Tiers (entities.ontology_tier)

| Tier | Label | Behavior |
|---|---|---|
| 0 | Locked | Taxes, payroll — cannot be delayed under any circumstances |
| 1 | Penalty | High-priority — max 25% deferral allowed |
| 2 | Relational | Partnership vendors — max 60% deferral allowed |
| 3 | Flexible | Low-priority — up to 100% deferral allowed |

---

## Prerequisites

- Node.js 18+
- Python 3.9+
- PostgreSQL 14+ (local or cloud, e.g. Supabase)
- A Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))
- (Optional) Twilio account for WhatsApp escalation alerts

---

## Environment Variables

Create a `.env` file at the root of the `cashpilot/` folder:

```env
# Required
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/cashpilot
GEMINI_API_KEY=your_gemini_api_key_here

# WhatsApp escalation (set to true to skip real Twilio calls)
WHATSAPP_MOCK_MODE=true
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+15551234567

# Set to true to reseed demo data every time the backend starts
AUTO_SEED_ON_STARTUP=false
```

If `DATABASE_URL` is missing or the database is unreachable, the backend automatically falls back to demo mode and serves mock data — the UI remains fully functional.

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd cashpilot
```

### 2. Set up the database

Create a PostgreSQL database and run the schema:

```bash
psql -U postgres -c "CREATE DATABASE cashpilot;"
psql -U postgres -d cashpilot -f schema.sql
```

### 3. Set up the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn python-multipart psycopg2-binary rapidfuzz google-generativeai python-dotenv twilio langchain
```

### 4. Set up the frontend

```bash
# From the cashpilot/ root
npm install
```

---

## Running the App

### Start the backend

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive Swagger docs are at `http://localhost:8000/docs`.

### Start the frontend

```bash
# From the cashpilot/ root
npm run dev
```

The UI will be available at `http://localhost:3000`.

> The Next.js app proxies API calls to the backend via `next.config.ts`. Make sure the backend is running before opening the frontend.

---

## Seeding Demo Data

To populate the database with realistic demo companies, vendors, clients, obligations, and transactions:

```bash
cd backend

# Run all setup scripts at once
python -m scripts.run_all

# Or run individually
python -m scripts.seed_data          # Creates companies, entities, obligations
python -m scripts.plaid_simulator    # Generates simulated bank transactions
python -m scripts.goodwill_scorer    # Calculates initial vendor goodwill scores
```

You can also set `AUTO_SEED_ON_STARTUP=true` in your `.env` to reseed automatically every time the backend starts.

---

## API Reference

### Ingestion
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ingest/receipt` | Upload a receipt image or PDF for OCR and reconciliation |

### Dashboard & UI
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard` | Cash vitals, sparkline, urgent actions, LP optimization |
| GET | `/api/inbox` | All pending AI-generated actions |
| GET | `/api/analytics` | 30-day cash flow, vendor goodwill, Monte Carlo |
| GET | `/api/transactions` | Recent transaction history |

### Quant Engine
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/quant/runway` | Days-to-Zero and 30-day daily projection |
| GET | `/api/quant/phantom` | Phantom usable cash (excluding locked obligations) |
| GET | `/api/quant/optimize` | LP payment optimization strategy |
| GET | `/api/quant/monte-carlo` | Monte Carlo survival probability |

### Simulation
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/simulate/advance` | Advance the simulated date by N days |

### AI Orchestrator
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/generate-payment-delay` | Draft a vendor payment extension email |
| POST | `/api/ai/generate-receivable-acceleration` | Draft an early payment incentive email |
| POST | `/api/ai/auto-generate` | Auto-generate actions from LP optimizer output |
| GET | `/api/ai/detect-zombie-spend` | Detect unused recurring subscriptions |
| POST | `/api/ai/generate-cancellation/{entity_id}` | Draft a subscription cancellation email |
| POST | `/api/ai/generate-debt-netting` | Draft a mutual balance netting proposal |
| POST | `/api/ai/generate-board-report` | Generate a one-click investor update |
| POST | `/api/ai/negotiate` | Run one round of multi-agent vendor negotiation |
| GET | `/api/ai/liquidation-options` | Get Shopify flash sale + Stripe factoring options |
| POST | `/api/ai/flash-sale` | Generate a Shopify flash sale payload |
| POST | `/api/ai/invoice-factoring` | Generate a Stripe invoice factoring payload |
| POST | `/api/ai/defcon1-whatsapp` | Trigger a Defcon 1 WhatsApp escalation alert |
| GET | `/api/ai/tools` | List all available LangChain tools |

---

## Key Concepts

### Days to Zero (D2Z)
A deterministic calculation that simulates the company's balance day-by-day over the next 30 days, applying all pending obligations on their due dates. The result is the exact number of days until the balance hits zero.

### Phantom Usable Cash
The gross bank balance minus all locked (Tier 0) obligations like taxes and payroll. This is the cash the business can actually spend or defer without legal/regulatory risk.

### LP Optimization
A linear programming solver that determines the optimal payment deferral strategy given the current cash position. It respects tier constraints (Tier 0 obligations are never touched) and goodwill scores to minimize relationship damage while maximizing cash preservation.

### Monte Carlo Simulation
Runs 10,000 scenarios with randomized variables — payment delays, invoice latency, and a 5% receivable default rate — to produce a probabilistic survival score and P10/Median/P90 balance projections.

### Goodwill Score
A 0–100 score per vendor/client that tracks relationship health. It increases when payments are made on time and decreases when payments are late. The AI uses this score to select the appropriate communication tone when drafting emails.

### Chain-of-Thought
Every AI-generated action includes a step-by-step reasoning trail stored in the database. This is displayed in the Action Inbox so users can understand exactly why the AI made a recommendation before approving or rejecting it.

### Human-in-the-Loop
No AI action is ever executed automatically. Every generated email draft, cancellation notice, or negotiation response is logged to `action_logs` with status `PENDING_USER` and must be explicitly approved by the user.

---

## Demo Mode

If `DATABASE_URL` is not set or the database is unreachable, the entire backend gracefully falls back to demo mode. All API endpoints return realistic mock data from `services/demo_mode.py`, and the frontend uses `mockState.ts` as a fallback. This means you can run and demo the full UI without any database setup.
