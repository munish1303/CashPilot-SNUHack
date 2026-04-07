from __future__ import annotations

from datetime import date, timedelta
from typing import Any


_STATE: dict[str, Any] = {
    "days_offset": 0,
    "simulated_as_of": date.today(),
}


def _projection(start_balance: float, slope: float, days: int, bump_every: int = 7, bump: float = 600) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(days):
        dt = _STATE["simulated_as_of"] + timedelta(days=i)
        balance = start_balance - slope * i + (bump if i > 0 and i % bump_every == 0 else 0)
        rows.append({"date": dt.isoformat(), "balance": round(balance, 2)})
    return rows


def _vitals() -> dict[str, Any]:
    offset = int(_STATE["days_offset"])
    total_bank = max(1200, 12450 - (offset * 220) + (offset // 5) * 180)
    phantom_usable = max(-2400, 4100 - (offset * 340) + (offset // 6) * 350)
    days_to_zero = max(1, 8 - offset // 3)
    return {
        "totalBank": int(total_bank),
        "phantomUsable": int(phantom_usable),
        "daysToZero": int(days_to_zero),
    }


def dashboard_payload() -> dict[str, Any]:
    vitals = _vitals()
    proj14 = _projection(float(vitals["phantomUsable"]), slope=420, days=14)

    return {
        "vitals": vitals,
        "actions": [
            {
                "id": "demo-a1",
                "title": "Fractionalize Acme Corp Payment",
                "subtitle": "$3,200 receivable · Due Thursday",
                "priority": "critical",
            },
            {
                "id": "demo-a2",
                "title": "Launch Shopify Flash Sale",
                "subtitle": "Projected +$2,100 revenue · 48 hrs",
                "priority": "high",
            },
            {
                "id": "demo-a3",
                "title": "Defer AWS Invoice $640",
                "subtitle": "Net-15 extension · Zero penalty",
                "priority": "medium",
            },
        ],
        "actionCount": 3,
        "sparkline": [{"day": row["date"], "phantom": row["balance"]} for row in proj14],
        "optimization": {
            "status": "DEMO_MODE",
            "optimized_obligations": [],
            "chain_of_thought": [
                {"label": "Demo Mode", "detail": "Database unavailable, using deterministic demo backend data."}
            ],
        },
    }


def runway_payload() -> dict[str, Any]:
    vitals = _vitals()
    projection = _projection(float(vitals["phantomUsable"]), slope=360, days=30)
    return {
        "days_to_zero": vitals["daysToZero"],
        "current_balance": vitals["totalBank"],
        "daily_projection": projection,
    }


def monte_carlo_payload() -> dict[str, Any]:
    vitals = _vitals()
    base = vitals["phantomUsable"]
    survival = max(5, min(95, 72 - (int(_STATE["days_offset"]) * 2)))
    return {
        "simulations": 10000,
        "survival_probability": survival,
        "p10_balance": round(base - 3200, 2),
        "median_balance": round(base - 900, 2),
        "p90_balance": round(base + 2600, 2),
    }


def analytics_payload() -> dict[str, Any]:
    runway = runway_payload()
    mc = monte_carlo_payload()

    cash_flow = []
    for idx, entry in enumerate(runway["daily_projection"][:30], start=1):
        cash_flow.append(
            {
                "day": f"D+{idx}",
                "standard": round(runway["current_balance"] - (idx * 290), 2),
                "phantom": round(entry["balance"], 2),
            }
        )

    return {
        "cashFlow": cash_flow,
        "vendors": [
            {"name": "Acme Corp", "goodwill": 95},
            {"name": "AWS", "goodwill": 78},
            {"name": "Shopify", "goodwill": 88},
            {"name": "FedEx", "goodwill": 55},
        ],
        "monteCarlo": {
            "simulations": mc["simulations"],
            "probability": mc["survival_probability"],
            "p10": mc["p10_balance"],
            "median": mc["median_balance"],
            "p90": mc["p90_balance"],
        },
        "optimization": {
            "status": "DEMO_MODE",
            "optimized_obligations": [],
        },
    }


def transactions_payload() -> dict[str, Any]:
    return {
        "items": [
            {
                "id": "demo-t1",
                "source": "Plaid Simulator",
                "description": "Home Depot - Purchase",
                "amount": -418.32,
                "date": "Jun 12",
                "matched": True,
                "confidence": 98,
                "matchedWith": "Scanned Receipt #HD-2024-0612",
            },
            {
                "id": "demo-t2",
                "source": "Stripe",
                "description": "Acme Corp - Invoice #1042",
                "amount": 3200.00,
                "date": "Jun 11",
                "matched": True,
                "confidence": 100,
                "matchedWith": "Stripe Webhook INV-1042",
            },
        ]
    }


def inbox_payload() -> dict[str, Any]:
    return {
        "inbox": [
            {
                "id": "demo-i1",
                "priority": "critical",
                "vendor": "CashPilot AI",
                "actionType": "Payment Follow-up",
                "summary": "Demo mode: defer AWS invoice by 15 days.",
                "chainOfThought": [
                    {"label": "Liquidity Gap", "detail": "Projected negative balance in 3 days."},
                    {"label": "Best Option", "detail": "Delay non-locked vendor payable to extend runway."},
                ],
                "payload": [{"label": "Delay Days", "detail": "15"}],
                "rawPayload": {},
                "executionType": "AI_GENERATED",
                "rawActionType": "PAYMENT_DELAY",
                "canGenerateDrafts": False,
                "hasCommunicationDraft": False,
            }
        ]
    }


def advance_simulation(days_offset: int) -> dict[str, Any]:
    if days_offset < 0 or days_offset > 30:
        raise ValueError("Offset must be between 0 and 30")

    today = date.today()
    _STATE["days_offset"] = days_offset
    _STATE["simulated_as_of"] = today + timedelta(days=days_offset)

    vitals = _vitals()
    return {
        "message": "Simulation advanced (demo mode)",
        "simulated_as_of": _STATE["simulated_as_of"].isoformat(),
        "new_balance": vitals["totalBank"],
        "resolved_obligations": 0,
        "new_obligations": 0,
        "breach_detected": vitals["phantomUsable"] < 0,
        "phantom_balance": vitals["phantomUsable"],
        "goodwill_updates": 0,
        "defcon1_escalation": {
            "triggered": False,
            "reason": "Demo mode without live DB/Twilio integration",
        },
    }
