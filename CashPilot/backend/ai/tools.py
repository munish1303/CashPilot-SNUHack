"""
LangChain Tools - Strict Function Calling for AI Agents (Feature 3).

Defines tools that CONSTRAIN the LLM to only access approved data sources.
The AI agent physically cannot make financial decisions — it can only
read data through these controlled interfaces.

Tools:
    - check_solvency: Check current company solvency status
    - get_vendor_goodwill: Get vendor relationship score
    - get_obligation_details: Get obligation payment details
    - run_lp_optimization: Run the LP optimizer (read-only)
    - get_entity_tier: Get entity ontology tier classification
    - generate_board_report: Generate an executive summary from dashboard and AI actions
"""

from langchain_core.tools import tool
from core.db import get_db_connection
from typing import Optional
import json


@tool
def check_solvency(company_id: Optional[str] = None) -> str:
    """Check current company solvency status including balance, phantom usable cash,
    runway days, and whether a liquidity breach is imminent.
    Use this to understand the company's financial health before drafting communications."""
    conn = get_db_connection()
    if not conn:
        return json.dumps({"error": "Database connection failed"})
    cur = conn.cursor()
    try:
        if company_id:
            cur.execute("SELECT id, plaid_current_balance, current_simulated_date FROM companies WHERE id = %s;", (company_id,))
        else:
            cur.execute("SELECT id, plaid_current_balance, current_simulated_date FROM companies LIMIT 1;")
        company = cur.fetchone()
        if not company:
            return json.dumps({"error": "Company not found"})

        balance = float(company["plaid_current_balance"])
        cid = str(company["id"])
        sim_date = company["current_simulated_date"]

        # Get locked obligations (Tier 0)
        cur.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) as locked FROM obligations WHERE status='PENDING' AND amount < 0 AND is_locked = TRUE;"
        )
        locked = float(cur.fetchone()["locked"])

        # Get total payables
        cur.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM obligations WHERE status='PENDING' AND amount < 0;"
        )
        total_payables = float(cur.fetchone()["total"])

        # Get total receivables
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM obligations WHERE status='PENDING' AND amount > 0;"
        )
        total_receivables = float(cur.fetchone()["total"])

        phantom_usable = balance - locked
        net_position = balance - total_payables + total_receivables
        is_breach = phantom_usable < 0

        return json.dumps({
            "company_id": cid,
            "simulated_date": sim_date.isoformat(),
            "bank_balance": round(balance, 2),
            "locked_obligations": round(locked, 2),
            "phantom_usable_cash": round(phantom_usable, 2),
            "total_payables": round(total_payables, 2),
            "total_receivables": round(total_receivables, 2),
            "net_position": round(net_position, 2),
            "is_liquidity_breach": is_breach,
            "runway_status": "CRITICAL" if is_breach else "HEALTHY" if phantom_usable > total_payables * 0.5 else "WARNING",
        })
    finally:
        cur.close()
        conn.close()


@tool
def get_vendor_goodwill(vendor_name: str) -> str:
    """Get a vendor's goodwill score (0-100), ontology tier, and relationship details.
    Use this to determine the appropriate communication tone before drafting emails."""
    conn = get_db_connection()
    if not conn:
        return json.dumps({"error": "Database connection failed"})
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, name, ontology_tier, goodwill_score, late_fee_rate, avg_latency_days
               FROM entities WHERE LOWER(name) LIKE %s AND entity_type = 'VENDOR' LIMIT 1;""",
            (f"%{vendor_name.lower()}%",),
        )
        vendor = cur.fetchone()
        if not vendor:
            return json.dumps({"error": f"Vendor '{vendor_name}' not found"})

        tier_labels = {0: "Locked (Immovable)", 1: "Penalty (Late fees)", 2: "Relational (Goodwill risk)", 3: "Flexible (Negotiable)"}
        tier = vendor["ontology_tier"]
        goodwill = vendor["goodwill_score"]

        # Tone recommendation
        if tier == 0:
            tone = "FORMAL_URGENT"
        elif goodwill >= 80:
            tone = "FRIENDLY_CONFIDENT"
        elif goodwill >= 50:
            tone = "PROFESSIONAL_RESPECTFUL"
        else:
            tone = "FORMAL_APOLOGETIC"

        return json.dumps({
            "vendor_id": str(vendor["id"]),
            "name": vendor["name"],
            "ontology_tier": tier,
            "tier_label": tier_labels.get(tier, "Unknown"),
            "goodwill_score": goodwill,
            "late_fee_rate": float(vendor["late_fee_rate"]) if vendor["late_fee_rate"] else 0.0,
            "avg_latency_days": vendor["avg_latency_days"],
            "recommended_tone": tone,
            "can_delay": tier >= 1,
            "max_delay_pct": {0: 0, 1: 25, 2: 60, 3: 100}.get(tier, 100),
        })
    finally:
        cur.close()
        conn.close()


@tool
def get_obligation_details(obligation_id: str) -> str:
    """Get detailed information about a specific obligation including amount,
    due date, associated entity, tier, and delay constraints.
    Use this before generating any communication about a specific payment."""
    conn = get_db_connection()
    if not conn:
        return json.dumps({"error": "Database connection failed"})
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT o.id, o.amount, o.due_date, o.status, o.is_locked,
                      e.name, e.entity_type, e.ontology_tier, e.goodwill_score, e.late_fee_rate
               FROM obligations o JOIN entities e ON o.entity_id = e.id
               WHERE o.id = %s;""",
            (obligation_id,),
        )
        ob = cur.fetchone()
        if not ob:
            return json.dumps({"error": f"Obligation {obligation_id} not found"})

        return json.dumps({
            "obligation_id": str(ob["id"]),
            "amount": float(ob["amount"]),
            "is_payable": float(ob["amount"]) < 0,
            "due_date": ob["due_date"].isoformat(),
            "status": ob["status"],
            "is_locked": ob["is_locked"],
            "entity_name": ob["name"],
            "entity_type": ob["entity_type"],
            "ontology_tier": ob["ontology_tier"],
            "goodwill_score": ob["goodwill_score"],
            "late_fee_rate": float(ob["late_fee_rate"]) if ob["late_fee_rate"] else 0.0,
        })
    finally:
        cur.close()
        conn.close()


@tool
def run_lp_optimization(company_id: Optional[str] = None) -> str:
    """Run the LP optimizer to get the optimal payment strategy.
    Returns which obligations should be delayed, by how much, and the estimated savings.
    This is READ-ONLY — it does not execute any payments."""
    from quant.optimizer import optimize_payment_strategy

    if not company_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()
        if not company:
            return json.dumps({"error": "Company not found"})
        company_id = str(company["id"])

    try:
        result = optimize_payment_strategy(company_id)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_entity_tier(entity_name: str) -> str:
    """Get the ontology tier classification for an entity.
    Tier 0 = Locked (taxes, payroll), Tier 1 = Penalty, Tier 2 = Relational, Tier 3 = Flexible.
    Use this to determine how aggressively we can negotiate with a vendor."""
    conn = get_db_connection()
    if not conn:
        return json.dumps({"error": "Database connection failed"})
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, ontology_tier, entity_type FROM entities WHERE LOWER(name) LIKE %s LIMIT 1;",
            (f"%{entity_name.lower()}%",),
        )
        entity = cur.fetchone()
        if not entity:
            return json.dumps({"error": f"Entity '{entity_name}' not found"})

        tier_constraints = {
            0: {"label": "Locked", "max_delay_pct": 0, "can_negotiate": False, "description": "Immovable obligations (taxes, payroll). Cannot be delayed."},
            1: {"label": "Penalty", "max_delay_pct": 25, "can_negotiate": True, "description": "Carries late fees. Delay cautiously up to 25%."},
            2: {"label": "Relational", "max_delay_pct": 60, "can_negotiate": True, "description": "Risk to goodwill. Negotiate respectfully, up to 60% delay."},
            3: {"label": "Flexible", "max_delay_pct": 100, "can_negotiate": True, "description": "Fully negotiable. Can defer 100% if needed."},
        }
        tier = entity["ontology_tier"]
        constraints = tier_constraints.get(tier, tier_constraints[3])

        return json.dumps({
            "entity_id": str(entity["id"]),
            "name": entity["name"],
            "entity_type": entity["entity_type"],
            "ontology_tier": tier,
            **constraints,
        })
    finally:
        cur.close()
        conn.close()


@tool
def generate_board_report(company_id: Optional[str] = None) -> str:
    """Generate a professional board or investor update using Contract 2
    (dashboard global state) and Contract 4 (recent AI actions)."""
    from ai.board_report import generate_board_report_payload

    try:
        return json.dumps(generate_board_report_payload(company_id), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Export all tools as a list for agent binding
ALL_TOOLS = [
    check_solvency,
    get_vendor_goodwill,
    get_obligation_details,
    run_lp_optimization,
    get_entity_tier,
    generate_board_report,
]
