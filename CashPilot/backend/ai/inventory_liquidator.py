"""
Inventory Liquidator - Emergency cash generation (Feature 16).

Mocks Shopify/Stripe API payloads for emergency inventory liquidation
as a last-resort cash generation strategy when the LP solver signals
critical liquidity breach.

Actions:
    - Flash sale generation (Shopify mock)
    - Invoice factoring (Stripe mock)
    - Emergency discount campaigns

ZERO AI FINANCIAL DECISIONS — generates execution payloads only.
"""

from typing import Dict, List
from core.db import get_db_connection
from datetime import timedelta
import json


def generate_flash_sale_payload(
    company_id: str,
    discount_percentage: float = 30.0,
    urgency_hours: int = 48,
) -> Dict:
    """
    Generate a Shopify-compatible flash sale payload.

    Mocks the creation of a time-limited discount campaign
    to liquidate inventory for emergency cash.

    Args:
        company_id: UUID of the company
        discount_percentage: Discount to offer (default 30%)
        urgency_hours: Hours until sale expires (default 48)

    Returns:
        Shopify-compatible payload + chain of thought
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT plaid_current_balance, current_simulated_date, name FROM companies WHERE id = %s;",
            (company_id,),
        )
        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")

        balance = float(company["plaid_current_balance"])
        sim_date = company["current_simulated_date"]

        # Get total pending payables to understand urgency
        cur.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM obligations WHERE status='PENDING' AND amount < 0;"
        )
        total_payables = float(cur.fetchone()["total"])

        shortfall = max(0, total_payables - balance)
        target_revenue = shortfall * 1.2  # Target 120% of shortfall

        # Mock Shopify payload
        shopify_payload = {
            "platform": "SHOPIFY",
            "api_version": "2024-01",
            "endpoint": "/admin/api/2024-01/price_rules.json",
            "method": "POST",
            "payload": {
                "price_rule": {
                    "title": f"EMERGENCY-FLASH-{sim_date.isoformat()}",
                    "target_type": "line_item",
                    "target_selection": "all",
                    "allocation_method": "across",
                    "value_type": "percentage",
                    "value": f"-{discount_percentage}",
                    "starts_at": sim_date.isoformat() + "T00:00:00Z",
                    "ends_at": (sim_date + timedelta(hours=urgency_hours)).isoformat() + "T23:59:59Z",
                    "usage_limit": None,
                    "customer_selection": "all",
                }
            },
            "mock": True,
            "estimated_revenue": round(target_revenue, 2),
        }

        chain_of_thought = [
            {"label": "Liquidity Gap", "detail": f"Current balance ${balance:,.2f} vs payables ${total_payables:,.2f} = ${shortfall:,.2f} shortfall."},
            {"label": "Strategy", "detail": f"Flash sale with {discount_percentage}% off for {urgency_hours} hours."},
            {"label": "Revenue Target", "detail": f"Need ${target_revenue:,.2f} in sales to bridge gap."},
            {"label": "Platform", "detail": "Shopify price rule API (mocked for hackathon)."},
        ]

        return {
            "action_type": "INVENTORY_LIQUIDATION",
            "sub_type": "SHOPIFY_FLASH_SALE",
            "shopify_payload": shopify_payload,
            "estimated_revenue": round(target_revenue, 2),
            "discount_percentage": discount_percentage,
            "urgency_hours": urgency_hours,
            "chain_of_thought": chain_of_thought,
            "requires_approval": True,
        }

    finally:
        cur.close()
        conn.close()


def generate_invoice_factoring_payload(
    company_id: str,
    factoring_rate: float = 3.0,
) -> Dict:
    """
    Generate a Stripe-compatible invoice factoring payload.

    Mocks selling outstanding receivables at a discount
    for immediate cash.

    Args:
        company_id: UUID of the company
        factoring_rate: Discount rate for factoring (default 3%)

    Returns:
        Stripe-compatible payload + chain of thought
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT plaid_current_balance, current_simulated_date FROM companies WHERE id = %s;",
            (company_id,),
        )
        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")

        sim_date = company["current_simulated_date"]

        # Get outstanding receivables
        cur.execute(
            """SELECT o.id, o.amount, o.due_date, e.name
               FROM obligations o
               JOIN entities e ON o.entity_id = e.id
               WHERE o.status = 'PENDING' AND o.amount > 0
               ORDER BY o.amount DESC LIMIT 10;"""
        )
        receivables = cur.fetchall()

        if not receivables:
            return {
                "action_type": "INVENTORY_LIQUIDATION",
                "sub_type": "STRIPE_INVOICE_FACTORING",
                "status": "NO_RECEIVABLES",
                "chain_of_thought": [
                    {"label": "Analysis", "detail": "No outstanding receivables to factor."},
                ],
            }

        factored_invoices = []
        total_face = 0
        total_cash = 0

        for r in receivables:
            face_value = float(r["amount"])
            discount = face_value * (factoring_rate / 100)
            cash_now = face_value - discount

            factored_invoices.append({
                "obligation_id": str(r["id"]),
                "client_name": r["name"],
                "face_value": round(face_value, 2),
                "factoring_discount": round(discount, 2),
                "cash_received": round(cash_now, 2),
                "due_date": r["due_date"].isoformat(),
            })
            total_face += face_value
            total_cash += cash_now

        # Mock Stripe payload
        stripe_payload = {
            "platform": "STRIPE",
            "api_version": "2024-01-01",
            "endpoint": "/v1/invoices/factoring",
            "method": "POST",
            "payload": {
                "invoices": [
                    {
                        "invoice_id": fi["obligation_id"],
                        "amount": fi["face_value"],
                        "discount_rate": factoring_rate,
                    }
                    for fi in factored_invoices
                ],
                "payout_method": "instant",
                "currency": "usd",
            },
            "mock": True,
            "estimated_payout": round(total_cash, 2),
        }

        chain_of_thought = [
            {"label": "Receivables Found", "detail": f"{len(factored_invoices)} invoices totaling ${total_face:,.2f}."},
            {"label": "Factoring Rate", "detail": f"{factoring_rate}% discount = ${round(total_face - total_cash, 2):,.2f} cost."},
            {"label": "Immediate Cash", "detail": f"${total_cash:,.2f} available immediately via Stripe payout."},
            {"label": "Platform", "detail": "Stripe invoice factoring API (mocked for hackathon)."},
        ]

        return {
            "action_type": "INVENTORY_LIQUIDATION",
            "sub_type": "STRIPE_INVOICE_FACTORING",
            "stripe_payload": stripe_payload,
            "factored_invoices": factored_invoices,
            "total_face_value": round(total_face, 2),
            "total_cash_received": round(total_cash, 2),
            "factoring_cost": round(total_face - total_cash, 2),
            "factoring_rate": factoring_rate,
            "chain_of_thought": chain_of_thought,
            "requires_approval": True,
        }

    finally:
        cur.close()
        conn.close()


def get_all_liquidation_options(company_id: str) -> Dict:
    """
    Get all available emergency liquidation options.
    Returns flash sale + invoice factoring payloads.
    """
    options = []

    try:
        flash = generate_flash_sale_payload(company_id)
        options.append(flash)
    except Exception as e:
        print(f"Flash sale generation failed: {e}")

    try:
        factoring = generate_invoice_factoring_payload(company_id)
        options.append(factoring)
    except Exception as e:
        print(f"Invoice factoring generation failed: {e}")

    total_potential = sum(
        o.get("estimated_revenue", 0) + o.get("total_cash_received", 0)
        for o in options
    )

    return {
        "liquidation_options": options,
        "total_potential_cash": round(total_potential, 2),
        "count": len(options),
    }
