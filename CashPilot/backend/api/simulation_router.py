from datetime import date, datetime, timedelta
import json
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.db import get_db_connection
from quant.phantom_balance import calculate_phantom_balance
from services import demo_mode

router = APIRouter()


class AdvanceRequest(BaseModel):
    days_offset: int


def _effective_clear_date(due_date: date, amount: float, latency_days: int) -> date:
    if amount < 0:
        return due_date
    return due_date + timedelta(days=max(0, latency_days))


def _ensure_future_obligations(cur, simulated_now: date, horizon_days: int = 45) -> int:
    """
    Keep a rolling pipeline of future receivables and payables so the dashboard
    continues to simulate a real business after the slider moves forward.
    """
    cur.execute(
        """
        SELECT id, name, entity_type, ontology_tier
        FROM entities
        ORDER BY name;
        """
    )
    entities = cur.fetchall()
    vendors = [entity for entity in entities if entity["entity_type"] == "VENDOR"]
    clients = [entity for entity in entities if entity["entity_type"] == "CLIENT"]

    created = 0
    for day_offset in range(1, horizon_days + 1):
        due_date = simulated_now + timedelta(days=day_offset)
        seed = int(due_date.strftime("%Y%m%d"))
        rng = random.Random(seed)

        cur.execute(
            "SELECT COUNT(*) AS c FROM obligations WHERE status = 'PENDING' AND due_date = %s;",
            (due_date,),
        )
        existing_count = int(cur.fetchone()["c"])

        if existing_count >= 3:
            continue

        # Recurring locked obligations.
        if due_date.day == 1 and vendors:
            vendor = next((entity for entity in vendors if entity["ontology_tier"] == 0), vendors[0])
            cur.execute(
                """
                INSERT INTO obligations (entity_id, amount, due_date, status, is_locked)
                VALUES (%s, %s, %s, 'PENDING', TRUE);
                """,
                (vendor["id"], round(rng.uniform(-2100.0, -2900.0), 2), due_date),
            )
            created += 1

        if due_date.day == 15 and len(vendors) > 1:
            payroll_vendor = next((entity for entity in vendors if entity["name"] == "Gusto Payroll"), vendors[1])
            cur.execute(
                """
                INSERT INTO obligations (entity_id, amount, due_date, status, is_locked)
                VALUES (%s, %s, %s, 'PENDING', TRUE);
                """,
                (payroll_vendor["id"], round(rng.uniform(-3200.0, -4700.0), 2), due_date),
            )
            created += 1

        # Everyday vendor bills.
        if vendors and rng.random() < 0.65:
            vendor = rng.choice(vendors)
            cur.execute(
                """
                INSERT INTO obligations (entity_id, amount, due_date, status, is_locked)
                VALUES (%s, %s, %s, 'PENDING', %s);
                """,
                (
                    vendor["id"],
                    round(rng.uniform(-90.0, -950.0), 2),
                    due_date,
                    vendor["ontology_tier"] <= 1,
                ),
            )
            created += 1

        # Less frequent surprise costs.
        if vendors and rng.random() < 0.18:
            vendor = rng.choice(vendors)
            cur.execute(
                """
                INSERT INTO obligations (entity_id, amount, due_date, status, is_locked)
                VALUES (%s, %s, %s, 'PENDING', FALSE);
                """,
                (vendor["id"], round(rng.uniform(-1200.0, -3500.0), 2), due_date),
            )
            created += 1

        # Receivables arrive on a separate cadence and can outweigh payables.
        if clients and rng.random() < 0.58:
            client = rng.choice(clients)
            if rng.random() < 0.30:
                receivable = round(rng.uniform(2400.0, 6200.0), 2)
            else:
                receivable = round(rng.uniform(250.0, 1800.0), 2)
            cur.execute(
                """
                INSERT INTO obligations (entity_id, amount, due_date, status, is_locked)
                VALUES (%s, %s, %s, 'PENDING', FALSE);
                """,
                (client["id"], receivable, due_date),
            )
            created += 1

    return created


@router.post("/api/simulate/advance")
def advance_simulation(request: AdvanceRequest):
    if request.days_offset < 0 or request.days_offset > 30:
        raise HTTPException(status_code=400, detail="Offset must be between 0 and 30")

    conn = get_db_connection()
    if not conn:
        try:
            return demo_mode.advance_simulation(request.days_offset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    cur = conn.cursor()
    try:
        today = datetime.now().date()
        target_date = today + timedelta(days=request.days_offset)

        cur.execute("SELECT id, plaid_current_balance, current_simulated_date FROM companies LIMIT 1;")
        company = cur.fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = company["id"]
        previous_date = company["current_simulated_date"]
        running_balance = float(company["plaid_current_balance"])
        resolved_count = 0
        reverted_count = 0

        if target_date < previous_date:
            cur.execute(
                """
                SELECT t.id AS transaction_id, t.amount, o.id AS obligation_id
                FROM transactions t
                JOIN obligations o
                  ON o.entity_id = t.entity_id
                 AND o.amount = t.amount
                 AND o.status = 'PAID'
                WHERE t.source = 'SIMULATION_ADVANCE'
                  AND t.cleared_date > %s
                  AND t.cleared_date <= %s
                ORDER BY t.cleared_date DESC;
                """,
                (target_date, previous_date),
            )
            for row in cur.fetchall():
                amount = float(row["amount"])
                cur.execute("DELETE FROM transactions WHERE id = %s;", (row["transaction_id"],))
                cur.execute("UPDATE obligations SET status = 'PENDING' WHERE id = %s;", (row["obligation_id"],))
                running_balance -= amount
                reverted_count += 1

        elif target_date > previous_date:
            cur.execute(
                """
                SELECT o.id, o.entity_id, o.amount, o.due_date, e.avg_latency_days
                FROM obligations o
                JOIN entities e ON e.id = o.entity_id
                WHERE o.status = 'PENDING'
                ORDER BY o.due_date ASC;
                """
            )
            for obligation in cur.fetchall():
                amount = float(obligation["amount"])
                clear_date = _effective_clear_date(
                    obligation["due_date"],
                    amount,
                    int(obligation["avg_latency_days"] or 0),
                )

                if previous_date < clear_date <= target_date:
                    cur.execute("UPDATE obligations SET status = 'PAID' WHERE id = %s;", (obligation["id"],))
                    cur.execute(
                        """
                        INSERT INTO transactions (entity_id, amount, cleared_date, source)
                        VALUES (%s, %s, %s, 'SIMULATION_ADVANCE');
                        """,
                        (obligation["entity_id"], amount, clear_date),
                    )
                    running_balance += amount
                    resolved_count += 1

        new_obligation_count = _ensure_future_obligations(cur, target_date)

        cur.execute(
            "UPDATE companies SET current_simulated_date = %s, plaid_current_balance = %s WHERE id = %s;",
            (target_date, round(running_balance, 2), company_id),
        )

        phantom = calculate_phantom_balance(str(company_id))
        breach_detected = phantom["usable_cash"] < 0 or running_balance < 500

        if breach_detected:
            cur.execute("SELECT id FROM action_logs WHERE action_type = 'URGENT' AND is_resolved = FALSE LIMIT 1;")
            existing = cur.fetchone()
            if not existing:
                chain = json.dumps(
                    {
                        "reason": f"Projected usable cash ${phantom['usable_cash']:,.2f}",
                        "current_balance": round(running_balance, 2),
                        "simulated_as_of": target_date.isoformat(),
                    }
                )
                message = (
                    f"LIQUIDITY BREACH: usable cash projected at ${phantom['usable_cash']:,.2f} on {target_date.isoformat()}"
                )
                cur.execute(
                    """
                    INSERT INTO action_logs (
                        company_id, action_type, message, status, chain_of_thought,
                        execution_type, execution_payload, created_at
                    )
                    VALUES (%s, 'URGENT', %s, 'PENDING_USER', %s, 'SYSTEM_ALERT', %s, %s);
                    """,
                    (
                        company_id,
                        message,
                        chain,
                        json.dumps({"action": "Review runway and defer non-locked payables"}),
                        target_date,
                    ),
                )
        else:
            cur.execute(
                """
                UPDATE action_logs
                SET is_resolved = TRUE, status = 'RESOLVED'
                WHERE action_type IN ('URGENT', 'HIGH') AND is_resolved = FALSE;
                """
            )

        conn.commit()

        escalation = None
        try:
            from services.whatsapp_escalation import maybe_send_defcon1_whatsapp

            escalation = maybe_send_defcon1_whatsapp(str(company_id))
        except Exception as escalation_error:
            escalation = {"triggered": False, "reason": f"Escalation failed: {escalation_error}"}

        return {
            "message": "Simulation advanced",
            "simulated_as_of": target_date.isoformat(),
            "new_balance": round(running_balance, 2),
            "resolved_obligations": resolved_count,
            "reverted_obligations": reverted_count,
            "new_obligations": new_obligation_count,
            "breach_detected": breach_detected,
            "phantom_balance": phantom["usable_cash"],
            "goodwill_updates": 0,
            "defcon1_escalation": escalation,
        }
    except Exception as exc:
        conn.rollback()
        print(f"Error in simulation advance: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()
        conn.close()
