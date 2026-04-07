import json
import os
import tempfile

import google.generativeai as genai
from dotenv import load_dotenv

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None


load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")


def process_pdf_to_contract(file_bytes: bytes) -> dict:
    """
    Process PDF invoice/bill and extract structured data.

    Args:
        file_bytes: PDF file content as bytes

    Returns:
        dict: Structured JSON matching ingestion_event schema
    """
    if pymupdf4llm is None:
        raise RuntimeError(
            "PDF ingestion requires the optional dependency 'pymupdf4llm'. "
            "Install it with: py -3 -m pip install pymupdf4llm"
        )

    print("Extracting layout-aware Markdown from PDF...")

    temp_pdf = None
    temp_pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(file_bytes)
            temp_pdf_path = temp_pdf.name

        md_text = pymupdf4llm.to_markdown(temp_pdf_path)

        prompt = f"""You are a financial data extractor. Below is a Markdown representation of a PDF invoice/bill.

Extract the details into this exact JSON structure:

{{
  "ingestion_event": {{
    "source": "PDF_OCR",
    "raw_text_reference": "Brief excerpt from the document",
    "parsed_data": {{
      "entity_name": "Name of the vendor or sender",
      "entity_type": "VENDOR",
      "amount": -100.00,
      "due_date": "YYYY-MM-DD",
      "is_receivable": false
    }},
    "reconciliation_confidence": 0.95
  }}
}}

CRITICAL RULES:
- Return ONLY valid JSON, no markdown code blocks.
- For INVOICES/BILLS you need to PAY: amount MUST be NEGATIVE (e.g., -1500.00)
- For RECEIPTS showing you already PAID: amount MUST be NEGATIVE (e.g., -1500.00)
- For INCOME/RECEIVABLES (money coming to you): amount should be positive
- If no due_date is found, use the invoice date or document date
- entity_type should be "VENDOR" for bills/invoices, "CUSTOMER" for receivables
- is_receivable should be false for money going OUT, true for money coming IN
- Set reconciliation_confidence between 0.0 and 1.0 based on data clarity
- Extract the exact vendor/entity name as it appears in the document

DATA:
{md_text}
"""

        print("Sending Markdown to Gemini for JSON structuring...")
        response = model.generate_content(prompt)

        try:
            json_str = response.text.replace("```json", "").replace("```", "").strip()
            parsed_json = json.loads(json_str)
            print("Successfully parsed PDF to structured data")
            return parsed_json
        except json.JSONDecodeError as exc:
            print(f"Failed to parse Gemini response as JSON: {exc}")
            print(f"Raw response: {response.text}")
            raise ValueError(f"Invalid JSON response from Gemini: {exc}") from exc

    except Exception as exc:
        error_msg = str(exc)
        print(f"Error processing PDF: {error_msg}")
        if "429" in error_msg or "quota" in error_msg.lower():
            raise Exception(
                "Gemini API quota exceeded. Please wait a few minutes or upgrade your API plan. "
                f"Error: {error_msg}"
            ) from exc
        raise Exception(f"PDF processing failed: {error_msg}") from exc
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.unlink(temp_pdf_path)
            except OSError:
                pass
