"""
Monte Carlo Simulator - Probabilistic survival analysis.

Runs randomized cash-flow paths across a 60-day horizon, accounting for:
  - Client payment delays based on avg_latency_days
  - Variance around those delays
  - A default probability on receivables
  - Immediate payment of payables on their due dates

Output: Survival probability (0-100%), P10/Median/P90 balances.

ZERO AI/LLM - Pure math only.
"""

from datetime import timedelta
from typing import Dict

import numpy as np

from core.db import get_db_connection


def run_monte_carlo_simulation(company_id: str, num_simulations: int = 10000, horizon_days: int = 60) -> Dict:
    """
    Runs Monte Carlo simulations to calculate probability of survival.
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

        initial_balance = float(company["plaid_current_balance"])
        simulated_now = company["current_simulated_date"]
        horizon = simulated_now + timedelta(days=horizon_days)

        cur.execute(
            """
            SELECT o.amount, o.due_date, e.avg_latency_days
            FROM obligations o
            JOIN entities e ON o.entity_id = e.id
            WHERE o.status = 'PENDING' AND o.due_date <= %s;
            """,
            (horizon,),
        )
        obligations = cur.fetchall()

        if not obligations:
            return {
                "simulations": num_simulations,
                "survival_probability": 100.0,
                "p10_balance": round(initial_balance, 2),
                "median_balance": round(initial_balance, 2),
                "p90_balance": round(initial_balance, 2),
                "horizon_days": horizon_days,
            }

        final_balances = np.zeros(num_simulations)
        minimum_balances = np.zeros(num_simulations)
        rng = np.random.default_rng(42)

        for sim in range(num_simulations):
            cash_flow = np.zeros(horizon_days + 1)

            for obligation in obligations:
                amount = float(obligation["amount"])
                due_date = obligation["due_date"]
                due_offset = max(0, min(horizon_days, (due_date - simulated_now).days))

                if amount < 0:
                    cash_flow[due_offset] += amount
                    continue

                latency = max(0, int(obligation["avg_latency_days"] or 0))
                variance = max(2, latency // 2 or 2)
                delayed_days = max(0, int(round(rng.normal(latency, variance))))

                if rng.random() <= 0.10:
                    continue

                receivable_offset = min(horizon_days, due_offset + delayed_days)
                cash_flow[receivable_offset] += amount

            balance_path = initial_balance + np.cumsum(cash_flow)
            final_balances[sim] = balance_path[-1]
            minimum_balances[sim] = np.min(balance_path)

        survival_count = int(np.sum(minimum_balances >= 0))

        return {
            "simulations": num_simulations,
            "survival_probability": round((survival_count / num_simulations) * 100, 2),
            "p10_balance": round(float(np.percentile(final_balances, 10)), 2),
            "median_balance": round(float(np.percentile(final_balances, 50)), 2),
            "p90_balance": round(float(np.percentile(final_balances, 90)), 2),
            "horizon_days": horizon_days,
        }
    finally:
        cur.close()
        conn.close()
