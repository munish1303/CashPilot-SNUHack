"""
Board report generation for investor and partner updates.

Pulls the dashboard state (Contract 2) plus recent AI actions (Contract 4),
then asks Gemini to format the context into an executive summary.
Falls back to deterministic templating if Gemini is unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from ai.action_generator import _generate_with_gemini
from core.db import get_db_connection
from quant.monte_carlo import run_monte_carlo_simulation
from quant.optimizer import optimize_payment_strategy
from quant.phantom_balance import calculate_phantom_balance
from quant.runway_engine import calculate_runway


def _safe_iso(value: Any) -> Optional[str]:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return None


def _normalize_recent_actions(rows: List[dict]) -> List[Dict[str, Any]]:
    normalized = []
    for row in rows:
        payload = row.get("execution_payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        cot = row.get("chain_of_thought") or {}
        if isinstance(cot, str):
            try:
                cot = json.loads(cot)
            except Exception:
                cot = {"reasoning": cot}

        step_details = []
        if isinstance(cot, dict) and isinstance(cot.get("steps"), list):
            for item in cot["steps"][:3]:
                if isinstance(item, dict):
                    detail = item.get("detail") or item.get("label")
                    if detail:
                        step_details.append(str(detail))
                elif item:
                    step_details.append(str(item))

        normalized.append(
            {
                "id": str(row["id"]),
                "action_type": row["action_type"],
                "message": row["message"],
                "status": row["status"],
                "created_at": _safe_iso(row.get("created_at")),
                "entity_name": payload.get("entity_name"),
                "communication_draft": payload.get("communication_draft"),
                "context": payload.get("context"),
                "reasoning_highlights": step_details,
            }
        )
    return normalized


def _build_contract_2(company_id: str) -> Dict[str, Any]:
    runway_data = calculate_runway(company_id)
    phantom_data = calculate_phantom_balance(company_id)

    try:
        optimization_data = optimize_payment_strategy(company_id)
    except Exception:
        optimization_data = {"status": "UNAVAILABLE", "optimized_obligations": []}

    try:
        monte_carlo_data = run_monte_carlo_simulation(company_id, num_simulations=5000)
    except Exception:
        monte_carlo_data = {
            "simulations": 5000,
            "survival_probability": None,
            "p10_balance": None,
            "median_balance": None,
            "p90_balance": None,
        }

    return {
        "simulated_as_of": (
            runway_data.get("daily_projection", [{}])[0].get("date")
            if runway_data.get("daily_projection")
            else None
        ),
        "plaid_balance": runway_data.get("current_balance"),
        "phantom_usable_cash": phantom_data.get("usable_cash"),
        "locked_tier_0_funds": phantom_data.get("locked_obligations"),
        "runway_metrics": {
            "days_to_zero": runway_data.get("days_to_zero"),
            "liquidity_breach_date": runway_data.get("breach_date"),
            "monte_carlo_survival_prob": monte_carlo_data.get("survival_probability"),
        },
        "cashflow_projection_array": [
            {"date": entry.get("date"), "balance": entry.get("balance")}
            for entry in runway_data.get("daily_projection", [])[:14]
        ],
        "optimization_summary": {
            "status": optimization_data.get("status"),
            "breach_prevented": optimization_data.get("breach_prevented"),
            "total_delayed": optimization_data.get("total_delayed"),
            "projected_savings": optimization_data.get("projected_savings"),
            "coverage_pct": optimization_data.get("coverage_pct"),
            "remaining_shortfall": optimization_data.get("remaining_shortfall"),
            "top_recommendations": [
                {
                    "entity_name": ob.get("entity_name"),
                    "delay_amount": ob.get("delay_amount"),
                    "pay_now": ob.get("pay_now"),
                    "new_due_date": ob.get("new_due_date"),
                    "ontology_tier": ob.get("ontology_tier"),
                }
                for ob in optimization_data.get("optimized_obligations", [])[:5]
                if ob.get("delay_amount", 0) > 0
            ],
        },
    }


def _build_contract_4(company_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, action_type, message, status, chain_of_thought, execution_payload, created_at
            FROM action_logs
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (company_id, limit),
        )
        rows = cur.fetchall()
        return _normalize_recent_actions(rows)
    finally:
        cur.close()
        conn.close()


def _fallback_report(contract_2: Dict[str, Any], contract_4: List[Dict[str, Any]]) -> str:
    runway = contract_2.get("runway_metrics", {}).get("days_to_zero")
    survival = contract_2.get("runway_metrics", {}).get("monte_carlo_survival_prob")
    phantom = contract_2.get("phantom_usable_cash")
    optimization = contract_2.get("optimization_summary", {})
    recommendations = optimization.get("top_recommendations", [])
    simulated_as_of = contract_2.get("simulated_as_of")

    summary = (
        f"As of {simulated_as_of}, runway is {runway} days and phantom usable cash stands at ${phantom:,.0f}."
        if simulated_as_of and runway is not None and phantom is not None
        else (
            f"Runway is currently {runway} days with phantom usable cash at ${phantom:,.0f}."
            if runway is not None and phantom is not None
            else "Cash position remains under active monitoring."
        )
    )

    bullets = []
    if recommendations:
        top = recommendations[0]
        bullets.append(
            f"- The optimizer's top intervention is to defer ${float(top.get('delay_amount') or 0):,.0f} "
            f"for {top.get('entity_name', 'a vendor')}, preserving near-term liquidity"
        )
        if top.get("new_due_date"):
            bullets[-1] += f" through {top['new_due_date']}"
        bullets[-1] += "."
    else:
        bullets.append("- No immediate payment deferrals are currently recommended.")

    if contract_4:
        latest = contract_4[0]
        when = latest.get("created_at")
        bullets.append(
            f"- Most recent AI action: {latest.get('action_type', 'AI action')} "
            f"logged on {when[:10] if when else 'the current simulation date'}"
            f" with status {latest.get('status', 'PENDING_USER')}."
        )
    else:
        bullets.append("- No recent AI actions have been logged yet.")

    if survival is not None:
        bullets.append(f"- Projected survival probability is {survival}%.")

    return "\n".join([summary, *bullets]).strip()


def generate_board_report_payload(company_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        raise ValueError("Database connection failed")

    cur = conn.cursor()
    try:
        if company_id:
            cur.execute(
                "SELECT id, name, current_simulated_date FROM companies WHERE id = %s;",
                (company_id,),
            )
        else:
            cur.execute("SELECT id, name, current_simulated_date FROM companies LIMIT 1;")

        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")

        resolved_company_id = str(company["id"])
        contract_2 = _build_contract_2(resolved_company_id)
        contract_4 = _build_contract_4(resolved_company_id)

        prompt = f"""You are writing a polished weekly investor or board update for a startup finance dashboard.

Use only the facts below. Write a concise executive summary in 1 short paragraph and then 3 bullet points.
Focus on cash health, AI interventions, risk mitigation, and next-step confidence.
Use explicit dates and concrete metrics. Sound calm, professional, and investor-ready.
Do not invent facts. If a value is missing, simply omit it.

Contract 2: Dashboard State
{json.dumps(contract_2, indent=2)}

Contract 4: Recent AI Actions
{json.dumps(contract_4, indent=2)}
"""

        narrative = _generate_with_gemini(prompt)
        if not narrative:
            narrative = _fallback_report(contract_2, contract_4)

        return {
            "company_id": resolved_company_id,
            "company_name": company["name"],
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source_contracts": {
                "contract_2": contract_2,
                "contract_4": contract_4,
            },
            "report": narrative.strip(),
        }
    finally:
        cur.close()
        conn.close()
