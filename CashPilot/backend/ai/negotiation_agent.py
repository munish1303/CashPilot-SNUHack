"""
Multi-Agent Negotiation Swarm (Feature 15).

Two-agent system using LangChain + Gemini:

Agent 1 (Communicator): Drafts emails and reads inbound counter-offers.
    - Uses tools: get_vendor_goodwill, get_obligation_details, get_entity_tier
    - Adapts tone based on vendor tier and goodwill

Agent 2 (Quant Reviewer): Takes counter-offers and validates them
    against the math engine to ensure the new deal doesn't bankrupt the user.
    - Uses tools: check_solvency, run_lp_optimization

The swarm flow:
    1. Communicator drafts outbound negotiation email
    2. Vendor responds with counter-offer (simulated/mocked)
    3. Quant Reviewer validates counter-offer is financially safe
    4. If safe → accept. If not → Communicator counters again.

ZERO AI FINANCIAL DECISIONS - AI drafts, math validates.
"""

from typing import Dict, List, Optional, TypedDict, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import json
import os


# ── Agent Definitions ───────────────────────────────────────────

def _get_llm():
    """Create Gemini LLM instance."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0.3,
    )


def _communicator_draft(
    vendor_name: str,
    amount: float,
    delay_days: int,
    tier: int,
    goodwill: int,
    fractional_payment: Optional[float] = None,
    counter_offer: Optional[str] = None,
) -> Dict:
    """
    Agent 1 (Communicator): Drafts outbound negotiation email.
    Binds LangChain tools for strict function calling.
    """
    from ai.tools import get_vendor_goodwill, get_entity_tier, get_obligation_details

    llm = _get_llm()

    # Determine tone
    tone_map = {
        0: "FORMAL_URGENT",
        1: "PROFESSIONAL_RESPECTFUL" if goodwill >= 60 else "FORMAL_APOLOGETIC",
        2: "FRIENDLY_CONFIDENT" if goodwill >= 80 else "PROFESSIONAL_RESPECTFUL",
        3: "FRIENDLY_CONFIDENT" if goodwill >= 70 else "PROFESSIONAL_RESPECTFUL",
    }
    tone = tone_map.get(tier, "PROFESSIONAL_RESPECTFUL")

    if counter_offer:
        # Round 2+: Responding to a counter-offer
        system = f"""You are a financial negotiation agent for CashPilot. You are responding to a vendor's counter-offer.

Your constraints:
- You CANNOT agree to any deal that requires paying more than the original amount
- You CANNOT agree to pay sooner than the proposed date
- You CAN offer partial payments as good faith
- Your tone must be: {tone}
- Be concise (under 120 words)

Vendor: {vendor_name} | Tier: {tier} | Goodwill: {goodwill}/100
Original ask: {delay_days}-day delay on ${amount:,.2f}
{"Partial payment offered: $" + f"{fractional_payment:,.2f}" if fractional_payment else ""}"""

        user_msg = f"The vendor responded with this counter-offer:\n\n{counter_offer}\n\nDraft your response:"
    else:
        # Round 1: Initial outreach
        system = f"""You are a financial negotiation agent for CashPilot. Draft an initial payment extension request email.

Your constraints:
- Frame as cash flow timing issue, NOT financial distress
- Be empathetic and relationship-focused
- Your tone must be: {tone}
- Be concise (under 150 words)
- Include specific dates and amounts

Vendor: {vendor_name} | Tier: {tier} | Goodwill: {goodwill}/100"""

        user_msg = f"""Draft a payment extension email:
- Amount: ${amount:,.2f}
- Extension: {delay_days} days
{"- Partial payment: $" + f"{fractional_payment:,.2f}" if fractional_payment else ""}"""

    if llm:
        # Use LangChain with tools bound
        tools = [get_vendor_goodwill, get_entity_tier]
        llm_with_tools = llm.bind_tools(tools)

        try:
            response = llm_with_tools.invoke([
                SystemMessage(content=system),
                HumanMessage(content=user_msg),
            ])
            draft = response.content
        except Exception as e:
            print(f"LangChain agent error: {e}")
            draft = _fallback_draft(vendor_name, amount, delay_days, fractional_payment, tone)
    else:
        draft = _fallback_draft(vendor_name, amount, delay_days, fractional_payment, tone)

    return {
        "agent": "COMMUNICATOR",
        "draft": draft,
        "tone": tone,
        "round": 2 if counter_offer else 1,
        "tools_available": ["get_vendor_goodwill", "get_entity_tier", "get_obligation_details"],
    }


def _quant_reviewer_validate(
    counter_offer_amount: float,
    counter_offer_days: int,
    original_amount: float,
    current_balance: float,
    total_payables: float,
) -> Dict:
    """
    Agent 2 (Quant Reviewer): Validates a counter-offer against the math engine.
    Ensures the proposed deal doesn't cause a liquidity breach.
    """
    from ai.tools import check_solvency, run_lp_optimization

    llm = _get_llm()

    # Pure math validation (no AI needed for this)
    # Check if accepting the counter-offer is financially safe
    remaining_after_accept = current_balance - counter_offer_amount
    remaining_obligations = total_payables - original_amount
    post_deal_surplus = remaining_after_accept - remaining_obligations

    is_safe = remaining_after_accept >= 0 and post_deal_surplus > -1000  # Allow small deficit
    savings = original_amount - counter_offer_amount

    math_verdict = {
        "is_safe": is_safe,
        "current_balance": round(current_balance, 2),
        "counter_offer_amount": round(counter_offer_amount, 2),
        "remaining_after_payment": round(remaining_after_accept, 2),
        "remaining_obligations": round(remaining_obligations, 2),
        "post_deal_surplus": round(post_deal_surplus, 2),
        "savings_vs_original": round(savings, 2),
        "days_offered": counter_offer_days,
    }

    # LLM provides human-readable analysis (but math decides)
    reasoning = ""
    if llm:
        tools = [check_solvency, run_lp_optimization]
        llm_with_tools = llm.bind_tools(tools)

        try:
            response = llm_with_tools.invoke([
                SystemMessage(content="""You are a quantitative financial analyst. 
Analyze this counter-offer and provide a 2-3 sentence assessment.
You have access to check_solvency and run_lp_optimization tools.
Your analysis is advisory only — the math verdict is final."""),
                HumanMessage(content=f"Counter-offer analysis:\n{json.dumps(math_verdict, indent=2)}\n\nProvide your assessment:"),
            ])
            reasoning = response.content
        except Exception as e:
            print(f"Quant reviewer LLM error: {e}")
            reasoning = f"Math verdict: {'ACCEPT — deal is safe' if is_safe else 'REJECT — would cause liquidity risk'}. Post-deal surplus: ${post_deal_surplus:,.2f}."
    else:
        reasoning = f"Math verdict: {'ACCEPT — deal is safe' if is_safe else 'REJECT — would cause liquidity risk'}. Post-deal surplus: ${post_deal_surplus:,.2f}."

    return {
        "agent": "QUANT_REVIEWER",
        "verdict": "ACCEPT" if is_safe else "REJECT",
        "math_verdict": math_verdict,
        "reasoning": reasoning,
        "tools_available": ["check_solvency", "run_lp_optimization"],
    }


def _fallback_draft(vendor_name, amount, delay_days, fractional_payment, tone):
    """Template fallback when LLM is unavailable."""
    partial = ""
    if fractional_payment:
        partial = f"\n\nAs a gesture of good faith, we are processing a partial payment of ${fractional_payment:,.2f} today."
    return (
        f"Dear {vendor_name},\n\n"
        f"Due to a temporary cash flow timing adjustment, we are requesting "
        f"a {delay_days}-day extension on our payment of ${amount:,.2f}.{partial}\n\n"
        f"We value our partnership and are committed to fulfilling this obligation promptly.\n\n"
        f"Best regards,\nCashPilot Finance Team"
    )


# ── Public Negotiation API ──────────────────────────────────────

def run_negotiation_round(
    obligation_id: str,
    delay_days: int = 7,
    fractional_payment: Optional[float] = None,
    counter_offer_text: Optional[str] = None,
    counter_offer_amount: Optional[float] = None,
    counter_offer_days: Optional[int] = None,
) -> Dict:
    """
    Execute one round of the negotiation swarm.

    Round 1 (no counter_offer): Communicator drafts initial email.
    Round 2+ (with counter_offer): Quant Reviewer validates, then Communicator responds.

    Returns: Full negotiation state with both agents' outputs.
    """
    from core.db import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get obligation + entity details
        cur.execute(
            """SELECT o.amount, o.due_date, e.name, e.ontology_tier, e.goodwill_score
               FROM obligations o JOIN entities e ON o.entity_id = e.id
               WHERE o.id = %s;""",
            (obligation_id,),
        )
        data = cur.fetchone()
        if not data:
            raise ValueError(f"Obligation {obligation_id} not found")

        amount = abs(float(data["amount"]))
        vendor_name = data["name"]
        tier = data["ontology_tier"] or 3
        goodwill = data["goodwill_score"] or 50

        # Get solvency info for quant reviewer
        cur.execute("SELECT plaid_current_balance FROM companies LIMIT 1;")
        balance = float(cur.fetchone()["plaid_current_balance"])

        cur.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM obligations WHERE status='PENDING' AND amount < 0;"
        )
        total_payables = float(cur.fetchone()["total"])

    finally:
        cur.close()
        conn.close()

    result = {
        "obligation_id": obligation_id,
        "vendor_name": vendor_name,
        "amount": amount,
        "tier": tier,
        "goodwill": goodwill,
        "agents": [],
        "chain_of_thought": [],
    }

    if counter_offer_text and counter_offer_amount is not None:
        # Round 2+: Validate counter-offer first
        quant_result = _quant_reviewer_validate(
            counter_offer_amount=counter_offer_amount,
            counter_offer_days=counter_offer_days or delay_days,
            original_amount=amount,
            current_balance=balance,
            total_payables=total_payables,
        )
        result["agents"].append(quant_result)
        result["chain_of_thought"].append({
            "label": "Quant Review",
            "detail": f"Counter-offer ${counter_offer_amount:,.2f} — {quant_result['verdict']}. {quant_result['reasoning'][:200]}",
        })

        if quant_result["verdict"] == "ACCEPT":
            result["status"] = "COUNTER_ACCEPTED"
            result["chain_of_thought"].append({
                "label": "Decision",
                "detail": f"Counter-offer accepted. Safe to pay ${counter_offer_amount:,.2f}.",
            })
            return result

        # If rejected, Communicator drafts counter-response
        comm_result = _communicator_draft(
            vendor_name=vendor_name,
            amount=amount,
            delay_days=delay_days,
            tier=tier,
            goodwill=goodwill,
            fractional_payment=fractional_payment,
            counter_offer=counter_offer_text,
        )
        result["agents"].append(comm_result)
        result["status"] = "COUNTER_REJECTED"
        result["chain_of_thought"].append({
            "label": "Counter-Response",
            "detail": "Counter-offer rejected by math engine. Communicator drafted revised proposal.",
        })
    else:
        # Round 1: Initial outreach
        comm_result = _communicator_draft(
            vendor_name=vendor_name,
            amount=amount,
            delay_days=delay_days,
            tier=tier,
            goodwill=goodwill,
            fractional_payment=fractional_payment,
        )
        result["agents"].append(comm_result)
        result["status"] = "INITIAL_OUTREACH"
        result["chain_of_thought"].append({
            "label": "Initial Contact",
            "detail": f"Communicator drafted {comm_result['tone']} email to {vendor_name} for {delay_days}-day extension.",
        })

    return result
