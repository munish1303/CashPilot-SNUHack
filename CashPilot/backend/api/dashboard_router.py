from fastapi import APIRouter, HTTPException
from datetime import timedelta
from core.db import get_db_connection
from quant.runway_engine import calculate_runway
from quant.optimizer import optimize_payment_strategy
from quant.monte_carlo import run_monte_carlo_simulation
import json
from services import demo_mode

router = APIRouter()


def _normalize_chain_of_thought(cot) -> list[dict]:
    steps = []

    if isinstance(cot, str):
        try:
            cot = json.loads(cot)
        except Exception:
            return [{"label": "Reasoning", "detail": cot}]

    if isinstance(cot, dict):
        if isinstance(cot.get("steps"), list):
            for i, item in enumerate(cot["steps"]):
                if isinstance(item, dict):
                    steps.append({
                        "label": str(item.get("label", f"Step {i + 1}")),
                        "detail": str(item.get("detail", "")),
                    })
                else:
                    steps.append({"label": f"Step {i + 1}", "detail": str(item)})
            return steps

        for key, value in cot.items():
            label = key.replace('_', ' ').title()
            detail = str(value) if value is not None else "N/A"
            steps.append({"label": label, "detail": detail})
        return steps

    if isinstance(cot, list):
        for i, item in enumerate(cot):
            if isinstance(item, dict):
                steps.append({
                    "label": str(item.get("label", f"Step {i + 1}")),
                    "detail": str(item.get("detail", "")),
                })
            else:
                steps.append({"label": f"Step {i + 1}", "detail": str(item)})

    return steps


def _normalize_payload(payload) -> tuple[list[dict], dict]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    if not isinstance(payload, dict):
        return [], {}

    payload_steps = []
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            continue
        label = key.replace('_', ' ').title()
        payload_steps.append({"label": label, "detail": str(value)})

    return payload_steps, payload

@router.get("/api/dashboard")
def get_dashboard():
    conn = get_db_connection()
    if not conn:
        return demo_mode.dashboard_payload()
        
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = str(company['id'])

        # Use quant modules for deterministic calculations
        runway_data = calculate_runway(company_id)

        # LP Optimizer — graceful fallback if it fails
        try:
            optimization_data = optimize_payment_strategy(company_id)
        except Exception:
            optimization_data = {"status": "UNAVAILABLE", "optimized_obligations": []}

        # Fetch urgent actions
        cur.execute("SELECT id, message as title, action_type as priority, status as subtitle FROM action_logs WHERE is_resolved = FALSE ORDER BY created_at DESC LIMIT 3;")
        actions_db = cur.fetchall()
        actions = []
        for a in actions_db:
            priority = 'high'
            if 'URGENT' in a['title']: priority = 'critical'
            actions.append({"id": str(a['id']), "title": a['title'], "subtitle": a['subtitle'] or "Pending", "priority": priority})

        # Count total unresolved actions for sidebar badge
        cur.execute("SELECT COUNT(*) as cnt FROM action_logs WHERE is_resolved = FALSE;")
        action_count = cur.fetchone()['cnt']

        # Build sparkline in the format the frontend expects: {day, phantom}
        sparkline = []
        for entry in runway_data['daily_projection'][:14]:
            sparkline.append({
                "day": entry['date'],
                "phantom": entry.get('usable_cash', entry['balance']),
            })

        return {
            "vitals": {
                "totalBank": runway_data['current_balance'],
                "phantomUsable": runway_data.get('current_usable_cash', runway_data['current_balance']),
                "daysToZero": runway_data['days_to_zero']
            },
            "actions": actions,
            "actionCount": action_count,
            "sparkline": sparkline,
            "optimization": optimization_data
        }
    finally:
        cur.close()
        conn.close()

@router.get("/api/inbox")
def get_inbox():
    conn = get_db_connection()
    if not conn:
        return demo_mode.inbox_payload()
        
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM action_logs WHERE is_resolved = FALSE ORDER BY id DESC;")
        logs = cur.fetchall()
        
        # Format for UI
        formatted_logs = []
        seen_draft_obligations = set()
        for log in logs:
            payload_steps, raw_payload = _normalize_payload(log['execution_payload'])
            obligation_id = raw_payload.get("obligation_id") if isinstance(raw_payload, dict) else None

            action_type_ui = "Payment Follow-up"
            if log['execution_type'] == 'SYSTEM_ALERT':
                action_type_ui = "System Alert"
            elif raw_payload.get("communication_draft"):
                action_type_ui = "AI Email Draft"

            if raw_payload.get("communication_draft") and obligation_id:
                obligation_key = str(obligation_id)
                if obligation_key in seen_draft_obligations:
                    continue
                seen_draft_obligations.add(obligation_key)

            # Normalize chain_of_thought into a consistent steps array
            steps = _normalize_chain_of_thought(log['chain_of_thought'])

            has_communication_draft = bool(raw_payload.get("communication_draft"))
            can_generate_drafts = (
                not has_communication_draft
                and log['execution_type'] != 'AI_GENERATED'
            )

            formatted_logs.append({
                "id": str(log['id']),
                "priority": "critical" if 'URGENT' in log['message'] else "high",
                "vendor": str(log.get('company_id', 'CashPilot AI')),
                "actionType": action_type_ui,
                "summary": log['message'],
                "chainOfThought": steps,
                "payload": payload_steps,
                "rawPayload": raw_payload,
                "executionType": log['execution_type'],
                "rawActionType": log['action_type'],
                "canGenerateDrafts": can_generate_drafts,
                "hasCommunicationDraft": has_communication_draft,
            })
            
        return {"inbox": formatted_logs}
    finally:
        cur.close()
        conn.close()

@router.get("/api/analytics")
def get_analytics():
    conn = get_db_connection()
    if not conn:
        return demo_mode.analytics_payload()

    cur = conn.cursor()
    try:
        cur.execute("SELECT id, plaid_current_balance, current_simulated_date FROM companies LIMIT 1;")
        company = cur.fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = str(company['id'])
        simulated_now = company['current_simulated_date']
        runway_data = calculate_runway(company_id)
        cash_flow = [
            {
                "day": (simulated_now + timedelta(days=index)).strftime("%b %d"),
                "standard": entry["balance"],
                "phantom": entry.get("usable_cash", entry["balance"]),
            }
            for index, entry in enumerate(runway_data["daily_projection"][:30])
        ]

        # Vendor goodwill radar (live from DB)
        cur.execute("SELECT name, goodwill_score FROM entities WHERE entity_type = 'VENDOR' ORDER BY ontology_tier ASC;")
        vendors = [{"name": v['name'], "goodwill": v['goodwill_score']} for v in cur.fetchall()]

        # Real Monte Carlo simulation using quant module
        try:
            monte_carlo_data = run_monte_carlo_simulation(company_id, num_simulations=10000)
        except Exception as e:
            # Fallback to placeholder if Monte Carlo fails
            print(f"Monte Carlo simulation failed: {e}")
            cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM obligations WHERE status = 'PENDING' AND amount < 0;")
            total_payables = abs(float(cur.fetchone()['total']))
            cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM obligations WHERE status = 'PENDING' AND amount > 0;")
            total_receivables = float(cur.fetchone()['total'])
            
            balance = float(company['plaid_current_balance'])
            survival = min(100, max(0, int((balance / max(total_payables, 1)) * 100)))
            monte_carlo_data = {
                "simulations": 10000,
                "survival_probability": survival,
                "p10_balance": round(balance - total_payables * 1.3, 2),
                "median_balance": round(balance - total_payables + total_receivables * 0.5, 2),
                "p90_balance": round(balance + total_receivables - total_payables * 0.5, 2)
            }

        # LP Optimization data
        try:
            optimization_data = optimize_payment_strategy(company_id)
        except Exception as e:
            print(f"LP optimization failed: {e}")
            optimization_data = {"status": "UNAVAILABLE", "optimized_obligations": []}

        return {
            "cashFlow": cash_flow,
            "vendors": vendors,
            "monteCarlo": {
                "simulations": monte_carlo_data.get("simulations", 10000),
                "probability": monte_carlo_data.get("survival_probability", 0),
                "p10": monte_carlo_data.get("p10_balance", 0),
                "median": monte_carlo_data.get("median_balance", 0),
                "p90": monte_carlo_data.get("p90_balance", 0)
            },
            "optimization": optimization_data
        }
    finally:
        cur.close()
        conn.close()


@router.get("/api/transactions")
def get_transactions():
    """Returns recent transactions from the live DB for the ingestion page."""
    conn = get_db_connection()
    if not conn:
        return demo_mode.transactions_payload()

    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT t.id, t.amount, t.cleared_date, t.source, e.name as entity_name, e.entity_type
            FROM transactions t
            JOIN entities e ON t.entity_id = e.id
            ORDER BY t.cleared_date DESC
            LIMIT 20;
        """)
        rows = cur.fetchall()
        
        items = []
        for r in rows:
            items.append({
                "id": str(r['id']),
                "source": r['source'].replace('_', ' ').title(),
                "description": f"{r['entity_name']} — {'Invoice' if float(r['amount']) > 0 else 'Payment'}",
                "amount": float(r['amount']),
                "date": r['cleared_date'].strftime("%b %d"),
                "matched": True,
                "confidence": 95 if r['source'] == 'PLAID_SIMULATOR' else 88,
                "matchedWith": f"Auto-reconciled via {r['source']}"
            })
        
        return {"items": items}
    finally:
        cur.close()
        conn.close()
