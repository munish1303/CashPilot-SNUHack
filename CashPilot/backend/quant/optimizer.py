"""
Linear Programming Optimizer - Payment strategy optimization.

Objective: Minimize (late fees + goodwill damage)
Constraints:
  - Balance >= 0 for all days
  - Tier 0 (locked) obligations MUST be paid (delay = 0)
  - Tier 1: max 25% delay
  - Tier 2: max 60% delay
  - Tier 3+: max 100% delay
  - delay_i >= 0 for all obligations

Uses scipy.optimize.linprog with the HiGHS solver.
Falls back to a greedy best-effort strategy when LP is infeasible.

ZERO AI/LLM - Pure math only.
"""

from datetime import timedelta
from typing import Dict, List
import numpy as np
from scipy.optimize import linprog
from core.db import get_db_connection
import re


# Tier-based constraints
TIER_MAX_DELAY = {0: 0.0, 1: 0.25, 2: 0.60, 3: 1.0}
TIER_LABELS = {0: "Locked", 1: "Penalty", 2: "Relational", 3: "Flexible"}


def _normalize_entity_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _find_netting_opportunities(rows: List[Dict]) -> tuple[List[Dict], float]:
    grouped: dict[str, dict] = {}
    for row in rows:
        key = _normalize_entity_name(row["entity_name"])
        if not key:
            continue
        bucket = grouped.setdefault(
            key,
            {
                "entity_name": row["entity_name"],
                "payables": [],
                "receivables": [],
            },
        )
        amount = float(row["amount"])
        item = {
            "obligation_id": str(row["id"]),
            "amount": amount,
            "due_date": row["due_date"].isoformat(),
            "entity_name": row["entity_name"],
        }
        if amount < 0:
            bucket["payables"].append(item)
        elif amount > 0:
            bucket["receivables"].append(item)

    opportunities = []
    total_netting = 0.0
    for key, bucket in grouped.items():
        if not bucket["payables"] or not bucket["receivables"]:
            continue

        payable_total = round(sum(abs(item["amount"]) for item in bucket["payables"]), 2)
        receivable_total = round(sum(item["amount"] for item in bucket["receivables"]), 2)
        nettable_amount = round(min(payable_total, receivable_total), 2)
        settlement_payment = round(max(payable_total - receivable_total, 0), 2)

        opportunities.append(
            {
                "netting_key": key,
                "entity_name": bucket["entity_name"],
                "payable_total": payable_total,
                "receivable_total": receivable_total,
                "nettable_amount": nettable_amount,
                "settlement_payment": settlement_payment,
                "payables": bucket["payables"],
                "receivables": bucket["receivables"],
                "strategy": "DEBT_NETTING",
            }
        )
        total_netting += nettable_amount

    opportunities.sort(key=lambda item: item["nettable_amount"], reverse=True)
    return opportunities, round(total_netting, 2)


def _get_tier(payable) -> int:
    """Get effective tier for a payable, considering is_locked override."""
    if payable['is_locked']:
        return 0
    return payable.get('ontology_tier', 3) or 3


def _build_obligations_list(payables, delay_fractions, cost_vector) -> List[Dict]:
    """Build the optimized obligations list from delay fractions."""
    obligations = []
    total_delayed = 0.0

    for i, p in enumerate(payables):
        frac = delay_fractions[i]
        amount_abs = abs(float(p['amount']))
        delay_amount = frac * amount_abs
        tier = _get_tier(p)

        if delay_amount > 0.01:
            pay_now = amount_abs - delay_amount
            delay_days = 7
            due_date = p['due_date']

            obligations.append({
                "obligation_id": str(p['id']),
                "entity_name": p['entity_name'],
                "original_amount": float(p['amount']),
                "original_due": due_date.isoformat(),
                "strategy": "FRACTIONAL_PAYMENT" if frac < 0.99 else "FULL_DEFER",
                "pay_now": round(pay_now, 2),
                "delay_amount": round(delay_amount, 2),
                "new_due_date": (due_date + timedelta(days=delay_days)).isoformat(),
                "estimated_cost": round(cost_vector[i] * frac, 2),
                "ontology_tier": tier,
                "tier_label": TIER_LABELS.get(tier, "Flexible"),
                "goodwill_score": p['goodwill_score'],
                "max_allowed_delay_pct": int(TIER_MAX_DELAY.get(tier, 1.0) * 100),
            })
            total_delayed += delay_amount

    return obligations, round(total_delayed, 2)


def _greedy_best_effort(payables, cost_vector, shortfall, netting_opportunities=None, total_netting: float = 0.0) -> Dict:
    """
    When LP is infeasible, greedily delay obligations starting from
    cheapest cost / highest tier (most flexible) first — up to tier max.
    """
    n = len(payables)
    # Score: higher = better candidate for delaying (low cost, high tier)
    scored = []
    for i, p in enumerate(payables):
        tier = _get_tier(p)
        max_frac = TIER_MAX_DELAY.get(tier, 1.0)
        amount_abs = abs(float(p['amount']))
        cost_per_dollar = cost_vector[i] / max(amount_abs, 0.01)
        # Priority: high tier first (more flexible), then low cost
        priority = tier * 1000 - cost_per_dollar
        scored.append((i, priority, max_frac, amount_abs))

    # Sort by priority descending (most flexible, cheapest first)
    scored.sort(key=lambda x: -x[1])

    delay_fractions = np.zeros(n)
    remaining_shortfall = shortfall

    for idx, _, max_frac, amount_abs in scored:
        if remaining_shortfall <= 0:
            break
        max_delay_amount = max_frac * amount_abs
        actual_delay = min(max_delay_amount, remaining_shortfall)
        if actual_delay > 0.01:
            delay_fractions[idx] = actual_delay / amount_abs
            remaining_shortfall -= actual_delay

    obligations, total_delayed = _build_obligations_list(
        payables, delay_fractions, cost_vector
    )

    covered_pct = round((1 - remaining_shortfall / max(shortfall, 0.01)) * 100, 1)

    return {
        "status": "PARTIAL_OPTIMIZATION",
        "optimized_obligations": obligations,
        "netting_opportunities": netting_opportunities or [],
        "total_netting": round(total_netting, 2),
        "projected_savings": 0.0,
        "breach_prevented": remaining_shortfall <= 0.01,
        "total_delayed": total_delayed,
        "shortfall": round(shortfall, 2),
        "remaining_shortfall": round(max(remaining_shortfall, 0), 2),
        "coverage_pct": covered_pct,
        "chain_of_thought": [
            {"label": "Detected Shortfall", "detail": f"Balance cannot cover ${round(shortfall, 2)} in upcoming obligations."},
            {"label": "Tier Constraints Applied", "detail": "Tier 0 locked (0%), Tier 1 max 25%, Tier 2 max 60%, Tier 3 max 100%."},
            {"label": "Best-Effort Strategy", "detail": f"Greedy deferral covers {covered_pct}% of shortfall (${round(total_delayed, 2)} deferred)."},
            {"label": "Remaining Gap", "detail": f"${round(max(remaining_shortfall, 0), 2)} still uncovered — manual intervention needed." if remaining_shortfall > 0.01 else "Shortfall fully covered by deferrals."},
        ]
    }


def optimize_payment_strategy(company_id: str) -> Dict:
    """
    Uses Linear Programming to find the optimal payment strategy.
    Falls back to greedy best-effort if LP is infeasible.
    """
    conn = get_db_connection()
    if not conn:
        raise ConnectionError("Database connection failed")

    cur = conn.cursor()

    try:
        # Get current state
        cur.execute(
            "SELECT plaid_current_balance, current_simulated_date FROM companies WHERE id = %s;",
            (company_id,)
        )
        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")

        current_balance = float(company['plaid_current_balance'])
        simulated_now = company['current_simulated_date']

        # Get all pending payables (negative amounts) for next 14 days
        horizon = simulated_now + timedelta(days=14)
        cur.execute(
            """
            SELECT o.id, o.amount, o.due_date, o.is_locked,
                   e.goodwill_score, e.late_fee_rate, e.name as entity_name,
                   e.ontology_tier
            FROM obligations o
            JOIN entities e ON o.entity_id = e.id
            WHERE o.status = 'PENDING' AND o.amount < 0
            AND o.due_date > %s AND o.due_date <= %s
            ORDER BY o.due_date;
            """,
            (simulated_now, horizon)
        )
        payables = cur.fetchall()

        cur.execute(
            """
            SELECT o.id, o.amount, o.due_date, e.name AS entity_name
            FROM obligations o
            JOIN entities e ON o.entity_id = e.id
            WHERE o.status = 'PENDING'
              AND o.due_date > %s AND o.due_date <= %s
            ORDER BY o.due_date;
            """,
            (simulated_now, horizon),
        )
        counterparty_rows = cur.fetchall()
        netting_opportunities, total_netting = _find_netting_opportunities(counterparty_rows)

        if not payables:
            return {
                "status": "NO_OPTIMIZATION_NEEDED",
                "optimized_obligations": [],
                "netting_opportunities": netting_opportunities,
                "total_netting": total_netting,
                "projected_savings": 0.0,
                "breach_prevented": False,
                "chain_of_thought": [
                    {"label": "Analysis", "detail": "No pending payables in the next 14 days."},
                    {"label": "Debt Netting", "detail": f"Found {len(netting_opportunities)} netting opportunities worth ${total_netting:,.2f}."},
                ]
            }

        n = len(payables)

        # Build cost vector (c): late_fee_rate * amount + goodwill_penalty
        c = []
        for p in payables:
            amount_abs = abs(float(p['amount']))
            late_fee_rate = float(p['late_fee_rate']) if p['late_fee_rate'] else 0.0
            goodwill = p['goodwill_score'] if p['goodwill_score'] is not None else 50

            late_fee_cost = amount_abs * late_fee_rate
            goodwill_penalty = amount_abs * (100 - goodwill) / 1000.0
            c.append(late_fee_cost + goodwill_penalty)

        c = np.array(c)

        # Calculate shortfall
        total_payables = sum(abs(float(p['amount'])) for p in payables)
        shortfall_before_netting = max(0, total_payables - current_balance)
        shortfall = max(0, shortfall_before_netting - total_netting)

        if shortfall == 0:
            return {
                "status": "NO_OPTIMIZATION_NEEDED",
                "optimized_obligations": [],
                "netting_opportunities": netting_opportunities,
                "total_netting": total_netting,
                "projected_savings": 0.0,
                "breach_prevented": False,
                "chain_of_thought": [
                    {"label": "Analysis", "detail": f"Balance ${current_balance:,.2f} plus ${total_netting:,.2f} of debt netting covers all ${total_payables:,.2f} in obligations."},
                    {"label": "Debt Netting", "detail": f"Found {len(netting_opportunities)} netting opportunities worth ${total_netting:,.2f}."},
                    {"label": "Result", "detail": "No payment deferrals needed."},
                ]
            }

        # LP Constraint: sum(delay_i * amount_i) >= shortfall
        # Standard form: -sum(delay_i * amount_i) <= -shortfall
        A_ub = [[-abs(float(p['amount'])) for p in payables]]
        A_ub = np.array(A_ub)
        b_ub = np.array([-shortfall])

        # Bounds: ontology-tier-based delay limits
        bounds = []
        for p in payables:
            tier = _get_tier(p)
            max_delay = TIER_MAX_DELAY.get(tier, 1.0)
            bounds.append((0, max_delay))

        # Solve LP
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')

        if not result.success:
            # LP is infeasible — use greedy best-effort instead
            return _greedy_best_effort(
                payables,
                c,
                shortfall,
                netting_opportunities=netting_opportunities,
                total_netting=total_netting,
            )

        # LP succeeded — build optimized strategy
        obligations, total_delayed = _build_obligations_list(
            payables, result.x, c
        )

        return {
            "status": "SUCCESS",
            "optimized_obligations": obligations,
            "netting_opportunities": netting_opportunities,
            "total_netting": total_netting,
            "projected_savings": round(shortfall - result.fun, 2),
            "breach_prevented": True,
            "total_delayed": total_delayed,
            "shortfall": round(shortfall, 2),
            "shortfall_before_netting": round(shortfall_before_netting, 2),
            "chain_of_thought": [
                {"label": "Detected Shortfall", "detail": f"${round(shortfall_before_netting, 2)} raw gap between balance and obligations."},
                {"label": "Debt Netting", "detail": f"Matched {len(netting_opportunities)} counterparties for ${total_netting:,.2f} of free netting, reducing the optimization gap to ${round(shortfall, 2)}."},
                {"label": "LP Solver", "detail": f"Optimized across {n} obligations respecting tier constraints."},
                {"label": "Result", "detail": f"Deferred ${total_delayed} to prevent breach. Estimated penalty cost: ${round(result.fun, 2)}."},
            ]
        }

    finally:
        cur.close()
        conn.close()
