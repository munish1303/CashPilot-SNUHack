"""
Action Generator - Context-aware communication drafting.

Takes LP optimizer output and generates vendor-specific communications
based on relationship history, tier classification, and goodwill scores.

Uses Google Gemini for natural language generation with template fallback.

ZERO FINANCIAL DECISIONS - Only translates math into language.
"""

import google.generativeai as genai
from typing import Dict, Optional
from core.db import get_db_connection
from datetime import timedelta
import os
import json

# Configure Gemini
_GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if _GEMINI_KEY:
    genai.configure(api_key=_GEMINI_KEY)

# Tone selection constants
TONE_MAP = {
    "FORMAL_URGENT": "Very formal, serious, time-sensitive tone",
    "FRIENDLY_CONFIDENT": "Warm, friendly, confident tone emphasizing partnership",
    "PROFESSIONAL_RESPECTFUL": "Professional and respectful, balanced tone",
    "FORMAL_APOLOGETIC": "Formal with an apologetic undertone, acknowledging inconvenience",
}


def _select_tone(tier: int, goodwill_score: int) -> str:
    """Select communication tone based on tier and goodwill."""
    if tier == 0:
        return "FORMAL_URGENT"
    elif goodwill_score >= 80:
        return "FRIENDLY_CONFIDENT"
    elif goodwill_score >= 50:
        return "PROFESSIONAL_RESPECTFUL"
    else:
        return "FORMAL_APOLOGETIC"


def _generate_with_gemini(prompt: str) -> Optional[str]:
    """Call Gemini API, return None on failure."""
    if not _GEMINI_KEY:
        return None
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None


def _template_payment_delay(context: dict) -> str:
    """Template fallback for payment delay email."""
    partial = ""
    if context.get("fractional_payment"):
        partial = (
            f"\n\nAs a gesture of good faith, we are processing a partial payment "
            f"of ${context['fractional_payment']:,.2f} today."
        )
    return (
        f"Dear {context['vendor_name']},\n\n"
        f"Due to a temporary cash flow timing adjustment, we are writing to request "
        f"a {context['delay_days']}-day extension on our upcoming payment of "
        f"${context['amount']:,.2f}, originally due {context['original_due']}."
        f"{partial}\n\n"
        f"We value our relationship and are committed to fulfilling this obligation "
        f"by {context['new_due_date']}.\n\n"
        f"Thank you for your understanding.\n\n"
        f"Best regards,\nCashPilot Finance Team"
    )


def _template_receivable_acceleration(context: dict) -> str:
    """Template fallback for receivable acceleration email."""
    return (
        f"Dear {context['client_name']},\n\n"
        f"We'd like to offer you an early payment incentive on Invoice "
        f"#{context.get('invoice_ref', 'pending')} for ${context['original_amount']:,.2f}, "
        f"originally due {context['original_due']}.\n\n"
        f"If you settle within {context['urgency_days']} days, we'll apply a "
        f"{context['discount_percentage']}% discount — saving you "
        f"${context['discount_amount']:,.2f}.\n\n"
        f"New amount: ${context['new_amount']:,.2f}\n\n"
        f"This offer is valid for the next {context['urgency_days']} days.\n\n"
        f"Best regards,\nCashPilot Finance Team"
    )


def _payment_delay_subject(context: dict) -> str:
    return (
        f"Request for {context['delay_days']}-day payment extension "
        f"for {context['vendor_name']}"
    )


def _receivable_acceleration_subject(context: dict) -> str:
    return (
        f"Early payment discount available for invoice {context['invoice_ref']}"
    )


def _template_debt_netting(context: dict) -> str:
    return (
        f"Dear {context['counterparty_name']},\n\n"
        f"Our ledger shows that we currently owe you ${context['payable_total']:,.2f}, while you owe us "
        f"${context['receivable_total']:,.2f}. Rather than moving funds in both directions, we'd like to net the balances.\n\n"
        f"After netting, we would wire ${context['settlement_payment']:,.2f} to settle both ledgers in full.\n\n"
        f"Please confirm and we will process the settlement today.\n\n"
        f"Best regards,\nCashPilot Finance Team"
    )


def _debt_netting_subject(context: dict) -> str:
    return f"Proposal to net mutual balances with {context['counterparty_name']}"


def generate_payment_delay_action(
    obligation_id: str,
    delay_days: int,
    fractional_payment: float = None,
) -> Dict:
    """
    Generates a contextual communication for delaying a payment.

    Args:
        obligation_id: UUID of the obligation
        delay_days: Number of days to delay
        fractional_payment: Optional partial payment amount

    Returns:
        Dict with action_type, communication_draft, tone, chain_of_thought, etc.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT o.amount, o.due_date,
                   e.name, e.entity_type, e.goodwill_score,
                   e.ontology_tier
            FROM obligations o
            JOIN entities e ON o.entity_id = e.id
            WHERE o.id = %s;
            """,
            (obligation_id,),
        )
        data = cur.fetchone()

        if not data:
            raise ValueError(f"Obligation {obligation_id} not found")

        amount = abs(float(data["amount"]))
        due_date = data["due_date"]
        goodwill = data["goodwill_score"] if data["goodwill_score"] is not None else 50
        tier = data["ontology_tier"] if data["ontology_tier"] is not None else 3

        tone = _select_tone(tier, goodwill)
        new_due_date = (due_date + timedelta(days=delay_days)).strftime("%B %d, %Y")

        context = {
            "vendor_name": data["name"],
            "amount": amount,
            "original_due": due_date.strftime("%B %d, %Y"),
            "delay_days": delay_days,
            "goodwill_score": goodwill,
            "tier": tier,
            "fractional_payment": fractional_payment,
            "new_due_date": new_due_date,
        }

        # Try Gemini first, fall back to template
        prompt = f"""You are a financial communication specialist. Draft a professional email requesting a payment extension.

Context:
- Vendor: {context['vendor_name']}
- Original Amount: ${context['amount']:,.2f}
- Original Due Date: {context['original_due']}
- Requested Extension: {delay_days} days (new due: {new_due_date})
- Relationship Quality: {goodwill}/100
- Tone: {TONE_MAP.get(tone, tone)}
{"- Partial Payment Offered: $" + f"{fractional_payment:,.2f}" if fractional_payment else ""}

Requirements:
1. Be concise (under 150 words)
2. Provide a clear reason (cash flow timing, not financial distress)
3. Offer specific new payment date
4. {"Emphasize the good-faith partial payment" if fractional_payment else "Express commitment to the relationship"}
5. Use appropriate tone: {tone}

Draft the email body only (no subject line):"""

        draft = _generate_with_gemini(prompt)
        if not draft:
            draft = _template_payment_delay(context)

        # Build chain of thought
        chain_of_thought = [
            {"label": "Obligation Identified", "detail": f"${amount:,.2f} due {context['original_due']} to {data['name']}."},
            {"label": "Tier Assessment", "detail": f"Tier {tier} — {'Locked (cannot delay)' if tier == 0 else 'Penalty (max 25% delay)' if tier == 1 else 'Relational (max 60%)' if tier == 2 else 'Flexible (max 100%)'}."},
            {"label": "Goodwill Score", "detail": f"{goodwill}/100 — {'Strong' if goodwill >= 70 else 'Moderate' if goodwill >= 40 else 'Weak'} relationship."},
            {"label": "Tone Selected", "detail": f"{tone} — {TONE_MAP.get(tone, 'Professional')}."},
            {"label": "Action", "detail": f"Request {delay_days}-day extension to {new_due_date}." + (f" Partial payment of ${fractional_payment:,.2f} today." if fractional_payment else "")},
        ]

        return {
            "action_type": "PAYMENT_DELAY",
            "obligation_id": obligation_id,
            "entity_name": data["name"],
            "communication_draft": draft,
            "email_from": "CashPilot Finance Team <admin@cashpilot.ai>",
            "email_to": f"Accounts Team, {data['name']}",
            "email_subject": _payment_delay_subject(context),
            "email_body": draft,
            "tone": tone,
            "chain_of_thought": chain_of_thought,
            "requires_approval": True,
            "context": {
                "amount": amount,
                "original_due": context["original_due"],
                "new_due_date": new_due_date,
                "delay_days": delay_days,
                "fractional_payment": fractional_payment,
                "tier": tier,
                "goodwill": goodwill,
            },
        }

    finally:
        cur.close()
        conn.close()


def generate_receivable_acceleration_action(
    obligation_id: str,
    discount_percentage: float,
    urgency_days: int,
) -> Dict:
    """
    Generates communication to incentivize early payment from clients.

    Args:
        obligation_id: UUID of the receivable
        discount_percentage: Discount offered for early payment (e.g., 3.0)
        urgency_days: Days until discount expires

    Returns:
        Dict with action_type, communication_draft, discount details, chain_of_thought
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT o.amount, o.due_date,
                   e.name, e.goodwill_score
            FROM obligations o
            JOIN entities e ON o.entity_id = e.id
            WHERE o.id = %s AND o.amount > 0;
            """,
            (obligation_id,),
        )
        data = cur.fetchone()

        if not data:
            raise ValueError(f"Receivable {obligation_id} not found")

        amount = float(data["amount"])
        discount_amount = amount * (discount_percentage / 100)
        new_amount = amount - discount_amount

        context = {
            "client_name": data["name"],
            "original_amount": amount,
            "discount_percentage": discount_percentage,
            "discount_amount": discount_amount,
            "new_amount": new_amount,
            "urgency_days": urgency_days,
            "original_due": data["due_date"].strftime("%B %d, %Y"),
            "invoice_ref": str(obligation_id)[:8],
        }

        prompt = f"""You are a financial communication specialist. Draft a professional email offering an early payment discount to a client.

Context:
- Client: {context['client_name']}
- Invoice Amount: ${amount:,.2f}
- Original Due Date: {context['original_due']}
- Early Payment Discount: {discount_percentage}% (${discount_amount:,.2f} savings)
- New Amount if Paid Early: ${new_amount:,.2f}
- Offer Valid For: {urgency_days} days

Requirements:
1. Be concise (under 120 words)
2. Frame as a win-win opportunity
3. Emphasize the savings amount
4. Create urgency with the deadline
5. Maintain positive tone

Draft the email body only (no subject line):"""

        draft = _generate_with_gemini(prompt)
        if not draft:
            draft = _template_receivable_acceleration(context)

        chain_of_thought = [
            {"label": "Receivable Identified", "detail": f"${amount:,.2f} due {context['original_due']} from {data['name']}."},
            {"label": "Discount Offered", "detail": f"{discount_percentage}% off = ${discount_amount:,.2f} savings for client."},
            {"label": "Net Benefit", "detail": f"Receive ${new_amount:,.2f} immediately vs ${amount:,.2f} on {context['original_due']}."},
            {"label": "Urgency", "detail": f"Offer valid for {urgency_days} days to accelerate cash inflow."},
        ]

        return {
            "action_type": "RECEIVABLE_ACCELERATION",
            "obligation_id": obligation_id,
            "entity_name": data["name"],
            "communication_draft": draft,
            "email_from": "CashPilot Finance Team <admin@cashpilot.ai>",
            "email_to": f"Finance Team, {data['name']}",
            "email_subject": _receivable_acceleration_subject(context),
            "email_body": draft,
            "discount_percentage": discount_percentage,
            "discount_amount": round(discount_amount, 2),
            "new_amount": round(new_amount, 2),
            "chain_of_thought": chain_of_thought,
            "requires_approval": True,
        }

    finally:
        cur.close()
        conn.close()


def generate_debt_netting_action(netting_key: str, company_id: Optional[str] = None) -> Dict:
    """
    Draft a debt netting proposal when the same counterparty is both a vendor and client.
    """
    from quant.optimizer import optimize_payment_strategy

    if not company_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()
        if not company:
            raise ValueError("Company not found")
        company_id = str(company["id"])

    optimization = optimize_payment_strategy(company_id)
    opportunity = next(
        (item for item in optimization.get("netting_opportunities", []) if item.get("netting_key") == netting_key),
        None,
    )
    if not opportunity:
        raise ValueError(f"Debt netting opportunity '{netting_key}' not found")

    context = {
        "counterparty_name": opportunity["entity_name"],
        "payable_total": float(opportunity["payable_total"]),
        "receivable_total": float(opportunity["receivable_total"]),
        "nettable_amount": float(opportunity["nettable_amount"]),
        "settlement_payment": float(opportunity["settlement_payment"]),
    }

    prompt = f"""You are a finance operations specialist. Draft a concise, professional email proposing debt netting with a counterparty.

Context:
- Counterparty: {context['counterparty_name']}
- We owe them: ${context['payable_total']:,.2f}
- They owe us: ${context['receivable_total']:,.2f}
- Nettable amount: ${context['nettable_amount']:,.2f}
- Settlement wire after netting: ${context['settlement_payment']:,.2f}

Requirements:
1. Keep it under 140 words
2. Explain that mutual balances can be netted to avoid unnecessary fund transfers
3. State the exact final settlement amount
4. Ask for confirmation to settle both ledgers today

Draft the email body only (no subject line):"""

    draft = _generate_with_gemini(prompt)
    if not draft:
        draft = _template_debt_netting(context)

    chain_of_thought = [
        {"label": "Counterparty Match", "detail": f"{context['counterparty_name']} appears as both vendor and client in the ledger."},
        {"label": "Mutual Exposure", "detail": f"We owe ${context['payable_total']:,.2f}; they owe us ${context['receivable_total']:,.2f}."},
        {"label": "Netting Benefit", "detail": f"Netting clears ${context['nettable_amount']:,.2f} without cash moving in both directions."},
        {"label": "Settlement", "detail": f"Proposed final wire is ${context['settlement_payment']:,.2f} to settle both ledgers."},
    ]

    return {
        "action_type": "DEBT_NETTING",
        "netting_key": netting_key,
        "entity_name": context["counterparty_name"],
        "communication_draft": draft,
        "email_from": "CashPilot Finance Team <admin@cashpilot.ai>",
        "email_to": f"Finance Team, {context['counterparty_name']}",
        "email_subject": _debt_netting_subject(context),
        "email_body": draft,
        "chain_of_thought": chain_of_thought,
        "requires_approval": True,
        "context": context,
    }
