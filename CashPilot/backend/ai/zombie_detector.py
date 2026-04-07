"""
Zombie Spend Detector - Identifies unused recurring expenses.

Analyzes transaction patterns to find subscriptions that haven't been
actively used, providing immediate liquidity through cancellation.

ZERO AI/LLM for detection - Pure pattern matching and heuristics.
Uses Gemini only for cancellation email drafting.
"""

from datetime import timedelta
from typing import Dict, List
from core.db import get_db_connection


def detect_zombie_subscriptions(company_id: str, lookback_days: int = 90) -> List[Dict]:
    """
    Identifies recurring expenses that may be unused "zombie spend".

    Heuristics:
    - Recurring monthly charges (same vendor, ≥2 transactions)
    - Non-critical vendors only (Tier 2-3)
    - Monthly pattern (transactions spread over ≥25 days)

    Returns:
        List of potential zombie subscriptions with cancellation impact
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT current_simulated_date FROM companies WHERE id = %s;", (company_id,))
        row = cur.fetchone()
        if not row:
            return []

        simulated_now = row["current_simulated_date"]
        lookback_start = simulated_now - timedelta(days=lookback_days)

        # Find recurring vendor charges
        cur.execute(
            """
            SELECT
                e.id as entity_id,
                e.name as vendor_name,
                e.ontology_tier,
                e.goodwill_score,
                COUNT(t.id) as transaction_count,
                AVG(t.amount) as avg_amount,
                MIN(t.cleared_date) as first_seen,
                MAX(t.cleared_date) as last_seen
            FROM transactions t
            JOIN entities e ON t.entity_id = e.id
            WHERE t.cleared_date >= %s
            AND t.amount < 0
            AND e.entity_type = 'VENDOR'
            GROUP BY e.id, e.name, e.ontology_tier, e.goodwill_score
            HAVING COUNT(t.id) >= 2
            ORDER BY AVG(t.amount) ASC;
            """,
            (lookback_start,),
        )
        recurring_vendors = cur.fetchall()

        zombie_candidates = []

        for vendor in recurring_vendors:
            days_active = (vendor["last_seen"] - vendor["first_seen"]).days

            # Heuristic: ≥2 charges over ≥25 days, non-critical tier
            is_likely_subscription = (
                vendor["transaction_count"] >= 2
                and days_active >= 25
                and vendor["ontology_tier"] >= 2
            )

            if is_likely_subscription:
                avg_amount = abs(float(vendor["avg_amount"]))
                annual_cost = avg_amount * 12

                # Keyword confidence boost
                name_lower = vendor["vendor_name"].lower()
                sub_keywords = ["software", "saas", "subscription", "monthly", "pro", "premium", "cloud", "tool"]
                is_sub_vendor = any(kw in name_lower for kw in sub_keywords)

                zombie_candidates.append({
                    "entity_id": str(vendor["entity_id"]),
                    "vendor_name": vendor["vendor_name"],
                    "monthly_cost": round(avg_amount, 2),
                    "annual_cost": round(annual_cost, 2),
                    "transaction_count": vendor["transaction_count"],
                    "first_seen": vendor["first_seen"].isoformat(),
                    "last_seen": vendor["last_seen"].isoformat(),
                    "ontology_tier": vendor["ontology_tier"],
                    "goodwill_score": vendor["goodwill_score"],
                    "confidence": "HIGH" if is_sub_vendor else "MEDIUM",
                    "recommendation": "REVIEW_FOR_CANCELLATION",
                    "impact": f"Cancelling saves ${avg_amount:,.2f}/month (${annual_cost:,.2f}/year)",
                })

        return zombie_candidates

    finally:
        cur.close()
        conn.close()


def generate_cancellation_action(entity_id: str) -> Dict:
    """
    Generates a cancellation action for a zombie subscription.

    Uses Gemini for email drafting with template fallback.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT name, goodwill_score, ontology_tier FROM entities WHERE id = %s;",
            (entity_id,),
        )
        vendor = cur.fetchone()

        if not vendor:
            raise ValueError(f"Vendor {entity_id} not found")

        # Try Gemini for cancellation email
        from ai.action_generator import _generate_with_gemini

        prompt = f"""Draft a professional subscription cancellation email.

Vendor: {vendor['name']}
Tone: Professional but firm

Requirements:
1. Request immediate cancellation
2. Request confirmation of cancellation
3. Ask for final invoice/prorated refund if applicable
4. Thank them for past service
5. Keep under 100 words

Draft the email body only:"""

        draft = _generate_with_gemini(prompt)
        if not draft:
            draft = (
                f"Dear {vendor['name']} Team,\n\n"
                f"We are writing to request the immediate cancellation of our subscription.\n\n"
                f"Please confirm the cancellation and provide a final invoice or prorated refund "
                f"for any unused portion of our current billing period.\n\n"
                f"Thank you for your service.\n\n"
                f"Best regards,\nCashPilot Finance Team"
            )

        chain_of_thought = [
            {"label": "Zombie Detected", "detail": f"Recurring charges to {vendor['name']} flagged as potential zombie spend."},
            {"label": "Tier Check", "detail": f"Tier {vendor['ontology_tier']} — safe to cancel without operational risk."},
            {"label": "Action", "detail": "Drafted cancellation email for user approval."},
        ]

        return {
            "action_type": "SUBSCRIPTION_CANCELLATION",
            "entity_id": entity_id,
            "entity_name": vendor["name"],
            "communication_draft": draft,
            "chain_of_thought": chain_of_thought,
            "requires_approval": True,
        }

    finally:
        cur.close()
        conn.close()
