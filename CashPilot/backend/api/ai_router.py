"""
AI Router - API endpoints for AI-powered actions (Stream 3).

All AI-generated actions are logged to the database for user review/approval.
No actions are executed automatically without user consent.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.db import get_db_connection
import json
from datetime import datetime

router = APIRouter()


# ── Request models ──────────────────────────────────────────────

class PaymentDelayRequest(BaseModel):
    obligation_id: str
    delay_days: int = 7
    fractional_payment: Optional[float] = None


class ReceivableAccelerationRequest(BaseModel):
    obligation_id: str
    discount_percentage: float = 3.0
    urgency_days: int = 5


class NegotiationRequest(BaseModel):
    obligation_id: str
    delay_days: int = 7
    fractional_payment: Optional[float] = None
    counter_offer_text: Optional[str] = None
    counter_offer_amount: Optional[float] = None
    counter_offer_days: Optional[int] = None


class LiquidationRequest(BaseModel):
    discount_percentage: float = 30.0
    urgency_hours: int = 48
    factoring_rate: float = 3.0


class AutoGenerateRequest(BaseModel):
    source_action_id: Optional[str] = None
    generate_all: bool = False


class DebtNettingRequest(BaseModel):
    netting_key: str
    company_id: Optional[str] = None


class BoardReportRequest(BaseModel):
    company_id: Optional[str] = None


class Defcon1Request(BaseModel):
    company_id: Optional[str] = None
    force: bool = False
    test_mode: bool = False
    test_company_name: str = "CashPilot Demo Co"
    test_days_to_zero: int = 2
    test_breach_label: str = "Friday"
    test_liquidation_amount: float = 2000.0


# ── Helper ──────────────────────────────────────────────────────

def _log_action_to_database(action: dict):
    """Log AI-generated actions to action_logs for user approval."""
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        if not company:
            return

        # Build chain_of_thought JSONB
        cot = action.get("chain_of_thought", [])
        if isinstance(cot, list):
            cot_json = json.dumps({"steps": cot})
        else:
            cot_json = json.dumps({"reasoning": str(cot)})

        # Build execution_payload
        payload = {
            k: v
            for k, v in action.items()
            if k not in ("chain_of_thought",)
        }

        # Truncate message to first 200 chars of draft
        draft_preview = action.get("communication_draft", action.get("sub_type", ""))[:200]
        message = f"[{action.get('action_type', 'AI')}] {action.get('entity_name', action.get('vendor_name', 'System'))}: {draft_preview}"

        cur.execute(
            """
            INSERT INTO action_logs (
                company_id, action_type, message, status,
                chain_of_thought, execution_type, execution_payload, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                company["id"],
                action.get("action_type", "AI_ACTION"),
                message,
                "PENDING_USER",
                cot_json,
                "AI_GENERATED",
                json.dumps(payload, default=str),
                datetime.now(),
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"Failed to log action: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def _fallback_draft_candidates(company_id: str) -> list[dict]:
    """
    Return upcoming non-locked payables as a fallback when optimizer output is
    unavailable or yields no delay recommendations.
    """
    conn = get_db_connection()
    if not conn:
        return []

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT o.id, o.amount, o.due_date, e.name AS entity_name, e.ontology_tier
            FROM obligations o
            JOIN entities e ON o.entity_id = e.id
            WHERE e.company_id = %s
              AND o.status = 'PENDING'
              AND o.amount < 0
              AND COALESCE(o.is_locked, FALSE) = FALSE
            ORDER BY o.due_date ASC, ABS(o.amount) DESC
            LIMIT 5;
            """,
            (company_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "obligation_id": str(row["id"]),
                "entity_name": row["entity_name"],
                "delay_amount": abs(float(row["amount"])),
                "pay_now": 0.0,
                "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
                "fallback_source": "UPCOMING_PAYABLE",
            }
            for row in rows
        ]
    finally:
        cur.close()
        conn.close()


def _draft_exists_for_obligation(company_id: str, obligation_id: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM action_logs
            WHERE company_id = %s
              AND is_resolved = FALSE
              AND action_type = 'PAYMENT_DELAY'
              AND execution_payload->>'obligation_id' = %s
            LIMIT 1;
            """,
            (company_id, obligation_id),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def _draft_exists_for_netting_key(company_id: str, netting_key: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM action_logs
            WHERE company_id = %s
              AND is_resolved = FALSE
              AND action_type = 'DEBT_NETTING'
              AND execution_payload->>'netting_key' = %s
            LIMIT 1;
            """,
            (company_id, netting_key),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


# ── Endpoints ───────────────────────────────────────────────────

@router.post("/api/ai/generate-payment-delay")
def generate_payment_delay(request: PaymentDelayRequest):
    """Generate a payment delay email using Gemini + log to DB."""
    try:
        from ai.action_generator import generate_payment_delay_action

        action = generate_payment_delay_action(
            request.obligation_id,
            request.delay_days,
            request.fractional_payment,
        )
        _log_action_to_database(action)
        return action
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/generate-receivable-acceleration")
def generate_receivable_acceleration(request: ReceivableAccelerationRequest):
    """Generate receivable acceleration email using Gemini + log to DB."""
    try:
        from ai.action_generator import generate_receivable_acceleration_action

        action = generate_receivable_acceleration_action(
            request.obligation_id,
            request.discount_percentage,
            request.urgency_days,
        )
        _log_action_to_database(action)
        return action
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ai/detect-zombie-spend")
def detect_zombie_spend():
    """Detect unused recurring subscriptions (zombie spend)."""
    try:
        from ai.zombie_detector import detect_zombie_subscriptions

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        zombies = detect_zombie_subscriptions(str(company["id"]))

        return {
            "zombie_subscriptions": zombies,
            "total_monthly_savings": round(sum(z["monthly_cost"] for z in zombies), 2),
            "total_annual_savings": round(sum(z["annual_cost"] for z in zombies), 2),
            "count": len(zombies),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/generate-cancellation/{entity_id}")
def generate_cancellation(entity_id: str):
    """Generate a subscription cancellation email."""
    try:
        from ai.zombie_detector import generate_cancellation_action

        action = generate_cancellation_action(entity_id)
        _log_action_to_database(action)
        return action
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ai/actions")
def get_pending_ai_actions():
    """Get all pending AI-generated actions awaiting user approval."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, action_type, message, status,
                   chain_of_thought, execution_payload, created_at
            FROM action_logs
            WHERE is_resolved = FALSE
            ORDER BY created_at DESC
            LIMIT 50;
            """
        )
        actions = cur.fetchall()

        formatted = []
        for a in actions:
            cot = a["chain_of_thought"]
            if isinstance(cot, str):
                try:
                    cot = json.loads(cot)
                except Exception:
                    cot = {"reasoning": cot}

            payload = a["execution_payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}

            formatted.append({
                "id": str(a["id"]),
                "action_type": a["action_type"],
                "message": a["message"],
                "status": a["status"],
                "chain_of_thought": cot,
                "execution_payload": payload,
                "created_at": a["created_at"].isoformat() if a["created_at"] else None,
            })

        cur.close()
        conn.close()

        return {"actions": formatted, "count": len(formatted)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/generate-debt-netting")
def generate_debt_netting(request: DebtNettingRequest):
    """Generate a debt netting settlement email using Gemini + log to DB."""
    try:
        from ai.action_generator import generate_debt_netting_action

        action = generate_debt_netting_action(request.netting_key, request.company_id)
        _log_action_to_database(action)
        return action
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/generate-board-report")
def generate_board_report(request: BoardReportRequest):
    """Generate a one-click investor update from dashboard state + recent AI actions."""
    try:
        from ai.board_report import generate_board_report_payload

        return generate_board_report_payload(request.company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/defcon1-whatsapp")
def trigger_defcon1_whatsapp(request: Defcon1Request):
    """Trigger the Defcon 1 WhatsApp escalation manually or for testing."""
    try:
        from services.whatsapp_escalation import maybe_send_defcon1_whatsapp, send_test_defcon1_whatsapp

        company_id = request.company_id
        if request.test_mode:
            return send_test_defcon1_whatsapp(
                company_id=company_id,
                company_name=request.test_company_name,
                days_to_zero=request.test_days_to_zero,
                breach_label=request.test_breach_label,
                liquidation_amount=request.test_liquidation_amount,
            )

        if not company_id:
            conn = get_db_connection()
            if not conn:
                raise HTTPException(status_code=500, detail="Database connection failed")
            cur = conn.cursor()
            cur.execute("SELECT id FROM companies LIMIT 1;")
            company = cur.fetchone()
            cur.close()
            conn.close()
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            company_id = str(company["id"])

        return maybe_send_defcon1_whatsapp(company_id, force=request.force)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/auto-generate")
def auto_generate_actions(request: AutoGenerateRequest):
    """
    Automatically generate AI actions from the LP optimizer output.
    Reads the current optimization result and creates actions for each
    vendor that needs a payment delay.
    """
    try:
        from quant.optimizer import optimize_payment_strategy

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = str(company["id"])
        optimization = optimize_payment_strategy(company_id)

        from ai.action_generator import generate_debt_netting_action, generate_payment_delay_action

        candidate_obligations = [
            ob for ob in optimization.get("optimized_obligations", [])
            if ob.get("delay_amount", 0) > 0.01
        ]
        netting_candidates = list(optimization.get("netting_opportunities", []))
        used_fallback = False

        if not candidate_obligations and not netting_candidates:
            candidate_obligations = _fallback_draft_candidates(company_id)
            used_fallback = len(candidate_obligations) > 0

        if not candidate_obligations and not netting_candidates:
            return {
                "message": "No draft candidates found",
                "optimization_status": optimization.get("status", "UNKNOWN"),
                "actions_generated": 0,
                "used_fallback": False,
                "errors": [],
            }

        candidates = [
            {"kind": "netting", "data": item}
            for item in netting_candidates
        ] + [
            {"kind": "payment_delay", "data": item}
            for item in candidate_obligations
        ]

        if not request.generate_all:
            candidates = candidates[:1]

        generated = []
        errors = []
        for candidate in candidates:
            try:
                if candidate["kind"] == "netting":
                    item = candidate["data"]
                    if _draft_exists_for_netting_key(company_id, item["netting_key"]):
                        errors.append(f"{item.get('entity_name', 'Unknown')}: debt netting draft already exists")
                        continue
                    action = generate_debt_netting_action(item["netting_key"], company_id)
                else:
                    ob = candidate["data"]
                    if _draft_exists_for_obligation(company_id, ob["obligation_id"]):
                        errors.append(f"{ob.get('entity_name', 'Unknown')}: draft already exists")
                        continue

                    pay_now = ob.get("pay_now")
                    action = generate_payment_delay_action(
                        ob["obligation_id"],
                        delay_days=7,
                        fractional_payment=pay_now if pay_now and pay_now > 0 else None,
                    )
                action["source_action_id"] = request.source_action_id
                action["generation_scope"] = "all" if request.generate_all else "single"
                _log_action_to_database(action)
                generated.append({
                    "entity_name": action.get("entity_name"),
                    "action_type": action["action_type"],
                    "tone": action.get("tone"),
                })
            except Exception as e:
                item = candidate["data"]
                entity_name = item.get("entity_name", "Unknown")
                error_message = f"{entity_name}: {str(e)}"
                print(f"Failed to generate action for {entity_name}: {e}")
                errors.append(error_message)

        return {
            "message": f"Generated {len(generated)} AI actions",
            "optimization_status": optimization.get("status", "UNKNOWN"),
            "actions_generated": len(generated),
            "used_fallback": used_fallback,
            "actions": generated,
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 15: Multi-Agent Negotiation ─────────────────────────

@router.post("/api/ai/negotiate")
def negotiate(request: NegotiationRequest):
    """
    Execute one round of the multi-agent negotiation swarm.

    Round 1 (no counter_offer): Communicator drafts initial email.
    Round 2+ (with counter_offer): Quant Reviewer validates → Communicator responds.
    """
    try:
        from ai.negotiation_agent import run_negotiation_round

        result = run_negotiation_round(
            obligation_id=request.obligation_id,
            delay_days=request.delay_days,
            fractional_payment=request.fractional_payment,
            counter_offer_text=request.counter_offer_text,
            counter_offer_amount=request.counter_offer_amount,
            counter_offer_days=request.counter_offer_days,
        )

        # Log the negotiation action
        _log_action_to_database({
            "action_type": "NEGOTIATION",
            "entity_name": result.get("vendor_name", "Unknown"),
            "communication_draft": result.get("agents", [{}])[0].get("draft", "")[:200] if result.get("agents") else "",
            "chain_of_thought": result.get("chain_of_thought", []),
        })

        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 16: Inventory Liquidation ───────────────────────────

@router.get("/api/ai/liquidation-options")
def get_liquidation_options():
    """Get all available emergency liquidation options (Shopify flash sale + Stripe factoring)."""
    try:
        from ai.inventory_liquidator import get_all_liquidation_options

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        result = get_all_liquidation_options(str(company["id"]))

        # Log each option
        for option in result.get("liquidation_options", []):
            _log_action_to_database(option)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/flash-sale")
def generate_flash_sale(request: LiquidationRequest):
    """Generate a Shopify flash sale payload for emergency inventory liquidation."""
    try:
        from ai.inventory_liquidator import generate_flash_sale_payload

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        result = generate_flash_sale_payload(
            str(company["id"]),
            discount_percentage=request.discount_percentage,
            urgency_hours=request.urgency_hours,
        )
        _log_action_to_database(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai/invoice-factoring")
def generate_invoice_factoring(request: LiquidationRequest):
    """Generate a Stripe invoice factoring payload for immediate cash."""
    try:
        from ai.inventory_liquidator import generate_invoice_factoring_payload

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies LIMIT 1;")
        company = cur.fetchone()
        cur.close()
        conn.close()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        result = generate_invoice_factoring_payload(
            str(company["id"]),
            factoring_rate=request.factoring_rate,
        )
        _log_action_to_database(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 3: LangChain Tools Introspection ───────────────────

@router.get("/api/ai/tools")
def list_tools():
    """List all available LangChain tools and their descriptions."""
    try:
        from ai.tools import ALL_TOOLS

        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                }
                for t in ALL_TOOLS
            ],
            "count": len(ALL_TOOLS),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

