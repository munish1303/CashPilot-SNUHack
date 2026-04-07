"""
Runway Engine - Deterministic "Days to Zero" (D2Z) calculation.

Algorithm: Day-by-day ledger simulation over a 60-day horizon.
Input: Current balance + pending obligations
Output: Days until phantom usable cash hits $0, breach date, daily projection

ZERO AI/LLM - Pure math only.
"""

from datetime import timedelta
from typing import Dict

from core.db import get_db_connection


def calculate_runway(company_id: str, horizon_days: int = 60, lock_horizon_days: int = 7) -> Dict:
    """
    Calculates the deterministic Days to Zero (D2Z) metric.

    Returns:
        {
            "days_to_zero": int,
            "breach_date": str (ISO format) or None,
            "daily_projection": List[Dict],
            "current_balance": float,
            "current_usable_cash": float
        }
    """
    conn = get_db_connection()
    if not conn:
        raise ConnectionError("Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT plaid_current_balance, current_simulated_date FROM companies WHERE id = %s;",
            (company_id,),
        )
        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")

        current_balance = float(company["plaid_current_balance"])
        simulated_now = company["current_simulated_date"]
        horizon = simulated_now + timedelta(days=horizon_days)

        cur.execute(
            """
            SELECT amount, due_date, is_locked
            FROM obligations
            WHERE status = 'PENDING' AND due_date <= %s
            ORDER BY due_date;
            """,
            (horizon,),
        )
        obligations = [
            {
                "amount": float(row["amount"]),
                "due_date": row["due_date"],
                "is_locked": bool(row["is_locked"]),
            }
            for row in cur.fetchall()
        ]

        daily_projection = []
        running_balance = current_balance
        breach_date = None
        days_to_zero = horizon_days

        def locked_reserve_for(day):
            lock_horizon = day + timedelta(days=lock_horizon_days)
            locked_total = sum(
                ob["amount"]
                for ob in obligations
                if ob["is_locked"] and day < ob["due_date"] <= lock_horizon
            )
            return abs(locked_total)

        opening_locked_reserve = locked_reserve_for(simulated_now)
        current_usable_cash = round(current_balance - opening_locked_reserve, 2)

        if current_usable_cash < 0:
            breach_date = simulated_now.isoformat()
            days_to_zero = 0

        for i in range(horizon_days):
            day = simulated_now + timedelta(days=i)
            day_net = sum(
                ob["amount"]
                for ob in obligations
                if (i == 0 and ob["due_date"] <= day) or (i > 0 and ob["due_date"] == day)
            )

            running_balance += day_net
            locked_reserve = locked_reserve_for(day)
            usable_cash = running_balance - locked_reserve

            daily_projection.append(
                {
                    "date": day.isoformat(),
                    "balance": round(running_balance, 2),
                    "usable_cash": round(usable_cash, 2),
                    "locked_reserve": round(locked_reserve, 2),
                    "day_net": round(day_net, 2),
                }
            )

            if usable_cash < 0 and breach_date is None:
                breach_date = day.isoformat()
                days_to_zero = i

        return {
            "days_to_zero": days_to_zero,
            "breach_date": breach_date,
            "daily_projection": daily_projection,
            "current_balance": round(current_balance, 2),
            "current_usable_cash": current_usable_cash,
            "horizon_days": horizon_days,
        }
    finally:
        cur.close()
        conn.close()
