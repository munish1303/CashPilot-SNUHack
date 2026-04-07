# PDF Invoice Processing

CashPilot now supports automated PDF invoice and bill processing using PyMuPDF4LLM and Gemini AI.

## Features

- **Layout-Aware Extraction**: Preserves tables, line items, and document structure
- **AI-Powered Parsing**: Uses Gemini 1.5 Pro to extract structured financial data
- **Automatic Reconciliation**: Matches invoices against existing obligations using fuzzy matching
- **Multi-Format Support**: Handles both images (JPG, PNG) and PDF documents

## How It Works

1. **PDF to Markdown**: PyMuPDF4LLM converts the PDF to structured Markdown, preserving layout
2. **AI Extraction**: Gemini analyzes the Markdown and extracts:
   - Vendor/entity name
   - Amount (positive for receivables, negative for payables)
   - Due date
   - Entity type (VENDOR/CUSTOMER)
3. **Reconciliation**: The system matches against pending obligations using:
   - Name similarity (>80% match using fuzzy matching)
   - Exact amount matching
4. **Action**: Either merges with existing obligation or creates a new pending one

## API Endpoint

```
POST /api/ingest/receipt
Content-Type: multipart/form-data
```

Accepts both image files and PDF documents.

## Testing

### Via Web Interface
1. Navigate to http://localhost:3000/ingestion
2. Drag and drop a PDF invoice or click to browse
3. Watch the real-time processing and reconciliation

### Via Python Script
```bash
cd cashpilot/backend
python test_pdf_processor.py
```

### Via API
```bash
curl -X POST http://localhost:8000/api/ingest/receipt \
  -F "file=@invoice.pdf"
```

## Response Format

```json
{
  "message": "PDF processed successfully",
  "file_type": "pdf",
  "parsed_receipt": {
    "ingestion_event": {
      "source": "PDF_OCR",
      "raw_text_reference": "Brief excerpt...",
      "parsed_data": {
        "entity_name": "Acme Corp",
        "entity_type": "VENDOR",
        "amount": -1250.00,
        "due_date": "2026-04-15",
        "is_receivable": false
      },
      "reconciliation_confidence": 0.95
    }
  },
  "reconciliation": {
    "status": "success",
    "action": "Merged with existing obligation 123",
    "entity": "Acme Corp",
    "amount": -1250.00
  }
}
```

## Dependencies

- `pymupdf4llm`: PDF to Markdown conversion with layout preservation
- `google-generativeai`: Gemini AI for intelligent data extraction
- `rapidfuzz`: Fuzzy string matching for entity reconciliation

All dependencies are automatically installed when you run:
```bash
pip install pymupdf4llm
```

## Notes

- PDF processing may take 2-5 seconds depending on document complexity
- The system handles multi-page invoices and complex table layouts
- Confidence scores help identify uncertain extractions for manual review
