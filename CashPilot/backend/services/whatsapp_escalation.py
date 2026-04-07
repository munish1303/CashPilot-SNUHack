"""
Defcon 1 WhatsApp escalation service.

When runway drops below a critical threshold, send a WhatsApp alert to the
business owner using Twilio or, if credentials are unavailable, a mock payload.
All escalation attempts are logged to action_logs for visibility in the UI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import base64
import json
import os

from core.db import get_db_connection
from quant.runway_engine import calculate_runway
from ai.inventory_liquidator import generate_flash_sale_payload


DEFCON_THRESHOLD_DAYS = 3
WHATSAPP_EXECUTION_TYPE = "WHATSAPP_ESCALATION"


def _get_company(company_id: str) -> dict:
    conn = get_db_connection()
    if not conn:
        raise ValueError("Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, current_simulated_date, plaid_current_balance FROM companies WHERE id = %s;",
            (company_id,),
        )
        company = cur.fetchone()
        if not company:
            raise ValueError("Company not found")
        return company
    finally:
        cur.close()
        conn.close()


def _existing_open_escalation(
    company_id: str,
    breach_date: Optional[str],
    days_to_zero: Optional[int] = None,
) -> Optional[dict]:
    conn = get_db_connection()
    if not conn:
        return None

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, execution_payload
            FROM action_logs
            WHERE company_id = %s
              AND execution_type = %s
              AND is_resolved = FALSE
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            (company_id, WHATSAPP_EXECUTION_TYPE),
        )
        row = cur.fetchone()
        if not row:
            return None

        payload = row.get("execution_payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        if breach_date and payload.get("breach_date") == breach_date:
            return {"id": str(row["id"]), "payload": payload}
        if not breach_date and days_to_zero is not None and payload.get("days_to_zero") == days_to_zero:
            return {"id": str(row["id"]), "payload": payload}
        return None
    finally:
        cur.close()
        conn.close()


def _choose_liquidation_recommendation(company_id: str) -> Dict[str, Any]:
    flash_sale = generate_flash_sale_payload(company_id, discount_percentage=20.0, urgency_hours=24)
    estimated_revenue = float(flash_sale.get("estimated_revenue", 0))

    return {
        "channel": "SHOPIFY_FLASH_SALE",
        "amount": round(min(max(estimated_revenue, 2000.0), 5000.0), 2),
        "payload": flash_sale.get("shopify_payload"),
        "summary": flash_sale.get("sub_type", "SHOPIFY_FLASH_SALE"),
    }


def _build_message(company: dict, runway_data: Dict[str, Any], recommendation: Dict[str, Any]) -> str:
    simulated_date = company["current_simulated_date"].strftime("%A, %b %d")
    breach_date = runway_data.get("breach_date")
    breach_label = breach_date if breach_date else simulated_date
    liquidation_amount = recommendation.get("amount", 0)

    return (
        f"Autopilot Alert: {company['name']} runway is down to {runway_data['days_to_zero']} day(s). "
        f"Projected payroll shortfall by {breach_label}. "
        f"Reply 'APPROVE' to liquidate ${liquidation_amount:,.0f} in Shopify inventory."
    )


def _build_test_message(
    company_name: str,
    days_to_zero: int,
    breach_label: str,
    liquidation_amount: float,
) -> str:
    return (
        f"Autopilot Alert: {company_name} runway is down to {days_to_zero} day(s). "
        f"Projected payroll shortfall by {breach_label}. "
        f"Reply 'APPROVE' to liquidate ${liquidation_amount:,.0f} in Shopify inventory."
    )


def _send_twilio_whatsapp(message: str) -> Dict[str, Any]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")
    to_number = os.getenv("TWILIO_WHATSAPP_TO")
    mock_mode = os.getenv("WHATSAPP_MOCK_MODE", "true").lower() == "true"

    if mock_mode or not all([account_sid, auth_token, from_number, to_number]):
        return {
            "status": "MOCK_SENT",
            "provider": "TWILIO_MOCK",
            "to": to_number or "whatsapp:+10000000000",
            "from": from_number or "whatsapp:+14155238886",
            "sid": None,
        }

    data = urlencode({
        "From": from_number,
        "To": to_number,
        "Body": message,
    }).encode("utf-8")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request = Request(url, data=data, method="POST")
    request.add_header("Authorization", f"Basic {auth}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return {
        "status": payload.get("status", "queued"),
        "provider": "TWILIO",
        "to": payload.get("to"),
        "from": payload.get("from"),
        "sid": payload.get("sid"),
    }


def _log_escalation(
    company_id: str,
    message: str,
    runway_data: Dict[str, Any],
    recommendation: Dict[str, Any],
    delivery: Dict[str, Any],
) -> str:
    conn = get_db_connection()
    if not conn:
        raise ValueError("Database connection failed")

    cur = conn.cursor()
    try:
        chain_of_thought = json.dumps({
            "steps": [
                {"label": "Trigger", "detail": f"Days to zero = {runway_data.get('days_to_zero')}."},
                {"label": "Threshold", "detail": f"Defcon 1 threshold is < {DEFCON_THRESHOLD_DAYS} days."},
                {
                    "label": "Recommendation",
                    "detail": f"Prepared {recommendation.get('summary', 'liquidation')} for ${recommendation.get('amount', 0):,.2f}.",
                },
                {"label": "Delivery", "detail": f"WhatsApp delivery status: {delivery.get('status', 'unknown')}."},
            ]
        })

        execution_payload = json.dumps(
            {
                "message": message,
                "days_to_zero": runway_data.get("days_to_zero"),
                "breach_date": runway_data.get("breach_date"),
                "delivery": delivery,
                "recommendation": recommendation,
            },
            default=str,
        )

        cur.execute(
            """
            INSERT INTO action_logs (
                company_id, action_type, message, status,
                chain_of_thought, execution_type, execution_payload, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                company_id,
                "DEFCON_1",
                f"[WHATSAPP] {message}",
                "PENDING_USER",
                chain_of_thought,
                WHATSAPP_EXECUTION_TYPE,
                execution_payload,
                datetime.now(),
            ),
        )
        action_id = str(cur.fetchone()["id"])
        conn.commit()
        return action_id
    finally:
        cur.close()
        conn.close()


def _resolve_company_id(company_id: Optional[str] = None) -> Optional[str]:
    if company_id:
        return company_id

    conn = get_db_connection()
    if not conn:
        return None

    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        return str(company["id"]) if company else None
    finally:
        cur.close()
        conn.close()


def maybe_send_defcon1_whatsapp(company_id: str, force: bool = False) -> Dict[str, Any]:
    company = _get_company(company_id)
    runway_data = calculate_runway(company_id)

    if not force and runway_data.get("days_to_zero", 99) >= DEFCON_THRESHOLD_DAYS:
        return {
            "triggered": False,
            "reason": f"Days to zero is {runway_data.get('days_to_zero')} (threshold: < {DEFCON_THRESHOLD_DAYS}).",
            "days_to_zero": runway_data.get("days_to_zero"),
        }

    breach_date = runway_data.get("breach_date")
    existing = _existing_open_escalation(
        company_id,
        breach_date,
        runway_data.get("days_to_zero"),
    )
    if existing and not force:
        return {
            "triggered": False,
            "reason": "Defcon 1 escalation already open for the current breach window.",
            "days_to_zero": runway_data.get("days_to_zero"),
            "existing_action_id": existing["id"],
        }

    recommendation = _choose_liquidation_recommendation(company_id)
    message = _build_message(company, runway_data, recommendation)
    delivery = _send_twilio_whatsapp(message)
    action_id = _log_escalation(company_id, message, runway_data, recommendation, delivery)

    return {
        "triggered": True,
        "company_id": company_id,
        "days_to_zero": runway_data.get("days_to_zero"),
        "breach_date": breach_date,
        "message": message,
        "delivery": delivery,
        "recommendation": recommendation,
        "action_log_id": action_id,
    }


def send_test_defcon1_whatsapp(
    company_id: Optional[str] = None,
    company_name: str = "CashPilot Demo Co",
    days_to_zero: int = 2,
    breach_label: str = "Friday",
    liquidation_amount: float = 2000.0,
) -> Dict[str, Any]:
    resolved_company_id = _resolve_company_id(company_id)
    message = _build_test_message(company_name, days_to_zero, breach_label, liquidation_amount)
    delivery = _send_twilio_whatsapp(message)

    action_id = None
    if resolved_company_id:
        runway_data = {"days_to_zero": days_to_zero, "breach_date": breach_label}
        recommendation = {
            "channel": "SHOPIFY_FLASH_SALE",
            "amount": round(liquidation_amount, 2),
            "payload": None,
            "summary": "SHOPIFY_FLASH_SALE_TEST",
        }
        action_id = _log_escalation(
            resolved_company_id,
            message,
            runway_data,
            recommendation,
            delivery,
        )

    return {
        "triggered": True,
        "test_mode": True,
        "company_id": resolved_company_id,
        "message": message,
        "delivery": delivery,
        "sample_payload": {
            "company_name": company_name,
            "days_to_zero": days_to_zero,
            "breach_label": breach_label,
            "liquidation_amount": liquidation_amount,
        },
        "action_log_id": action_id,
    }
