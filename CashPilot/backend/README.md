# CashPilot - Backend

This folder contains the backend services for the CashPilot AI-driven financial autopilot. This implementation specifically covers **Stream 1: The Perception Layer**.

## Requirements

Ensure you have Python 3.9+ installed. It is recommended to use a virtual environment.

```bash
cd backend
python -m venv venv
# On Windows
venv\Scripts\activate
# On Mac/Linux
source venv/bin/activate
```

### Dependencies
Install the required packages:

```bash
pip install fastapi uvicorn python-multipart psycopg2-binary rapidfuzz google-generativeai python-dotenv
```

## Setup & Configuration

1. Make sure your `.env` file is located at the **root** of the monorepo (`../.env` relative to this folder).
2. The `.env` file must contain:
   ```env
   DATABASE_URL=postgresql://postgres:user@host:5432/postgres
   GEMINI_API_KEY=your_gemini_api_key_here
   WHATSAPP_MOCK_MODE=true
   TWILIO_ACCOUNT_SID=your_twilio_sid_here
   TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   TWILIO_WHATSAPP_TO=whatsapp:+15551234567
   ```

If Twilio credentials are missing, the Defcon 1 escalation automatically falls back to mock mode and still logs the WhatsApp payload into `action_logs`.

## Running the Data Scripts

We have provided simulation scripts to populate the database and simulate background transactions.

To run the full suite (Seed Data, Simulate Plaid Transactions, and Vendor Goodwill Scoring):
```bash
# Ensure you are in the backend directory
python -m scripts.run_all
```

Alternatively, you can run them individually:
- `python -m scripts.seed_data`
- `python -m scripts.plaid_simulator`
- `python -m scripts.goodwill_scorer`

## Running the API Server

To start the FastAPI server, run:
```bash
# Ensure you are in the backend directory
uvicorn main:app --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000).
Swagger UI Documentation will be at [http://localhost:8000/docs](http://localhost:8000/docs).

## Available Endpoints

### `POST /api/ingest/receipt`
Accepts a multipart form data upload of a receipt image.
- **Workflow:** Passes the image to `gemini-1.5-pro` for strict JSON extraction matching the `ingestion_event` schema.
- Uses `rapidfuzz` to evaluate supplier name (String similarity > 80%) AND matches the exact `amount`.
- If match: Merges record into pending `obligations` and creates a `transaction`.
- If not matched: Creates a new pending `obligation`.
