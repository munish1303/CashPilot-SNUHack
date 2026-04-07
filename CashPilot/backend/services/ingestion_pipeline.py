import os
import json
import re
from datetime import date, datetime
from typing import Optional
import google.generativeai as genai
from rapidfuzz import fuzz

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db_connection

# Ensure API key is configured
api_key = os.environ.get("GEMINI_API_KEY", "")
if api_key:
    genai.configure(api_key=api_key)


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        return text[7:-3].strip()
    if text.startswith("```"):
        return text[3:-3].strip()
    return text


def _is_placeholder_value(value) -> bool:
    if value is None:
        return True
    normalized = str(value).strip().lower()
    return normalized in {"", "unknown", "unknown vendor", "not found", "n/a", "none", "null"}


def _is_invalid_amount(value) -> bool:
    if value is None:
        return True
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return True
    return abs(numeric) < 0.009


def _normalize_due_date(value) -> Optional[str]:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_amount_from_text(text: str):
    prioritized_patterns = [
        r"(?i)(?:total|amount due|balance due|grand total|net amount)[:\s$]*([\d,]+\.\d{2})",
        r"(?i)(?:subtotal)[:\s$]*([\d,]+\.\d{2})",
    ]

    prioritized = []
    for pattern in prioritized_patterns:
        for match in re.findall(pattern, text):
            try:
                prioritized.append(float(match.replace(",", "")))
            except ValueError:
                continue

    if prioritized:
        return -max(prioritized)

    matches = re.findall(r"(?<!\d)(\d[\d,]*\.\d{2})(?!\d)", text)
    numeric = []
    for match in matches:
        try:
            value = float(match.replace(",", ""))
            if value > 0.5:
                numeric.append(value)
        except ValueError:
            continue
    return -max(numeric) if numeric else None


def _extract_vendor_from_text(text: str):
    lines = [line.strip(" -*\t") for line in text.splitlines() if line.strip()]
    for line in lines[:10]:
        lowered = line.lower()
        if any(char.isalpha() for char in line) and "total" not in lowered and "invoice" not in lowered and "receipt" not in lowered:
            return line[:120]
    return None


def _extract_date_from_text(text: str):
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1)

    named = re.search(r"\b([A-Za-z]{3,9}\s+\d{1,2},\s+20\d{2})\b", text)
    if named:
        return _normalize_due_date(named.group(1))

    numeric = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b", text)
    if numeric:
        return _normalize_due_date(numeric.group(1))
    return None


def _normalize_parsed_receipt(parsed: dict) -> dict:
    event = parsed.setdefault("ingestion_event", {})
    pd = event.setdefault("parsed_data", {})
    raw_text = str(event.get("raw_text_reference") or "")

    if _is_placeholder_value(pd.get("entity_name")):
        pd["entity_name"] = _extract_vendor_from_text(raw_text) or "Unknown Vendor"

    if _is_invalid_amount(pd.get("amount")):
        extracted_amount = _extract_amount_from_text(raw_text)
        if extracted_amount is not None:
            pd["amount"] = extracted_amount

    normalized_due_date = _normalize_due_date(pd.get("due_date"))
    if normalized_due_date:
        pd["due_date"] = normalized_due_date
    else:
        pd["due_date"] = _extract_date_from_text(raw_text) or date.today().isoformat()

    if _is_placeholder_value(pd.get("entity_type")):
        pd["entity_type"] = "VENDOR"

    if not event.get("reconciliation_confidence"):
        event["reconciliation_confidence"] = 0.7

    parsed["ingestion_event"] = event
    return parsed


def parse_receipt_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Uses Gemini 1.5 Pro to parse receipt image into strict JSON.
    Expected schema matches ingestion_event from shared_contracts.json.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is not set in the environment.")

    model = genai.GenerativeModel('gemini-2.5-flash')

    prompt = '''
    Analyze this receipt image and extract the data into a strict JSON payload.
    Do not include markdown blocks, only raw JSON.
    The JSON structure MUST exactly match this format:
    {
        "ingestion_event": {
            "source": "GEMINI_VISION_OCR",
            "raw_text_reference": "Extracted text snippet...",
            "parsed_data": {
                "entity_name": "Name of the Vendor",
                "entity_type": "VENDOR",
                "amount": -123.45,
                "due_date": "YYYY-MM-DD"
            },
            "reconciliation_confidence": 0.95
        }
    }
    
    CRITICAL RULES:
    - Use the merchant or vendor name for entity_name
    - For INVOICES/BILLS/RECEIPTS showing money PAID or OWED: amount MUST be NEGATIVE (e.g., -123.45)
    - For INCOME/RECEIVABLES (money coming to you): amount should be positive
    - Use the final total or amount due for amount
    - If no due date exists, use the transaction/receipt date. If no date visible, use today's date
    - raw_text_reference should contain the OCR text you relied on
    - Return ONLY valid JSON, no markdown code blocks
    '''
    image_parts = [
        {
            "mime_type": mime_type,
            "data": image_bytes
        }
    ]

    response = model.generate_content([prompt, image_parts[0]])
    try:
        parsed = json.loads(_strip_markdown_fence(response.text))
        return _normalize_parsed_receipt(parsed)
    except Exception as e:
        error_msg = str(e)
        print("Failed to parse Gemini output:", response.text if hasattr(response, 'text') else error_msg)
        
        # Check if it's a quota error
        if "429" in error_msg or "quota" in error_msg.lower():
            raise ValueError(f"Gemini API quota exceeded. Please wait a few minutes or upgrade your API plan.")
        raise e


def reconcile_receipt(parsed_data: dict) -> dict:
    """
    N-Way Reconciliation: Uses rapidfuzz to check scanned receipts against the obligations table.
    Matches if Amount matches AND Name similarity > 80%.
    If matched -> Merge records.
    If no match -> Create new pending obligation.
    """
    event = parsed_data.get('ingestion_event', parsed_data)
    pd = event.get('parsed_data', {})

    amount = pd.get('amount')
    entity_name = pd.get('entity_name')
    due_date = pd.get('due_date')

    if not amount or not entity_name or not due_date:
        raise ValueError("Missing required fields in parsed receipt data.")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, name FROM entities WHERE entity_type = 'VENDOR';")
        entities = cur.fetchall()

        matched_entity_id = None
        for entity in entities:
            if fuzz.ratio(entity['name'].lower(), entity_name.lower()) > 80:
                matched_entity_id = entity['id']
                break

        if not matched_entity_id:
            cur.execute("SELECT id FROM companies LIMIT 1;")
            company = cur.fetchone()
            if company:
                cur.execute(
                    "INSERT INTO entities (company_id, name, entity_type, ontology_tier) "
                    "VALUES (%s, %s, %s, %s) RETURNING id;",
                    (company['id'], entity_name, 'VENDOR', 3)
                )
                matched_entity_id = cur.fetchone()['id']
            else:
                raise Exception("No company found to associate new entity with.")

        cur.execute("SELECT id, amount FROM obligations WHERE status = 'PENDING' AND entity_id = %s;", (matched_entity_id,))
        pending_obs = cur.fetchall()

        matched_ob_id = None
        for ob in pending_obs:
            if abs(float(ob['amount']) - float(amount)) < 0.01:
                matched_ob_id = ob['id']
                break

        if matched_ob_id:
            cur.execute("UPDATE obligations SET status = 'PAID' WHERE id = %s;", (matched_ob_id,))
            cur.execute(
                "INSERT INTO transactions (entity_id, amount, cleared_date, source) "
                "VALUES (%s, %s, CURRENT_DATE, %s);",
                (matched_entity_id, amount, 'RECEIPT_OCR')
            )
            result_action = f"Merged with existing obligation {matched_ob_id}"
        else:
            cur.execute(
                "INSERT INTO obligations (entity_id, amount, due_date, status) "
                "VALUES (%s, %s, %s, %s) RETURNING id;",
                (matched_entity_id, amount, due_date, 'PENDING')
            )
            new_id = cur.fetchone()['id']
            result_action = f"Created new pending obligation {new_id}"

        conn.commit()

        return {
            "status": "success",
            "action": result_action,
            "entity": entity_name,
            "amount": amount
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
