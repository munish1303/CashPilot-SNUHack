"""
Phantom Balance Calculator - Virtual liability ring-fencing.

Formula: Usable Cash = Total Balance - Locked Tier 0 Obligations
Input:  Total balance + locked obligations within horizon
Output: Money you can actually spend

ZERO AI/LLM - Pure math only.
"""

from datetime import timedelta
from typing import Dict
from core.db import get_db_connection


def calculate_phantom_balance(company_id: str, horizon_days: int = 7) -> Dict:
    """
    Calculates the Phantom Usable Cash by subtracting locked obligations.

    Args:
        company_id: UUID of the company
        horizon_days: Number of days to look ahead (default 7)

    Returns:
        {
            "total_balance": float,
            "locked_obligations": float,
            "usable_cash": float,
            "horizon_date": str
        }
    """
    conn = get_db_connection()
    if not conn:
        raise ConnectionError("Database connection failed")

    cur = conn.cursor()

    try:
        # Get current balance
        cur.execute(
            "SELECT plaid_current_balance, current_simulated_date FROM companies WHERE id = %s;",
            (company_id,)
        )
        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")

        total_balance = float(company['plaid_current_balance'])
        simulated_now = company['current_simulated_date']
        horizon = simulated_now + timedelta(days=horizon_days)

        # Sum all locked (Tier 0) obligations within horizon
        # Locked obligations are payables (negative amounts)
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) as locked_total "
            "FROM obligations "
            "WHERE status = 'PENDING' AND is_locked = TRUE "
            "AND due_date > %s AND due_date <= %s;",
            (simulated_now, horizon)
        )
        locked_total = float(cur.fetchone()['locked_total'])

        # Usable cash = total balance + locked_total (locked_total is negative for payables)
        usable_cash = total_balance + locked_total

        return {
            "total_balance": round(total_balance, 2),
            "locked_obligations": round(abs(locked_total), 2),
            "usable_cash": round(usable_cash, 2),
            "horizon_date": horizon.isoformat()
        }

    finally:
        cur.close()
        conn.close()
