from fastapi import APIRouter, UploadFile, File, HTTPException
import traceback
from services.ingestion_pipeline import parse_receipt_image, reconcile_receipt
from services.pdf_processor import process_pdf_to_contract

router = APIRouter()

@router.post("/api/ingest/receipt")
async def ingest_receipt(file: UploadFile = File(...)):
    """
    Triggers the OCR pipeline for images and PDFs:
    1. Parses the file using Gemini (Vision OCR for images, PDF parser for PDFs).
    2. Runs N-Way Reconciliation on the extracted data.
    """
    # Check if file is image or PDF
    is_pdf = file.content_type == "application/pdf" or (file.filename and file.filename.lower().endswith('.pdf'))
    is_image = file.content_type and file.content_type.startswith("image/")
    
    if not is_pdf and not is_image:
        raise HTTPException(
            status_code=400, 
            detail="File must be an image (JPG, PNG) or PDF document."
        )
        
    try:
        contents = await file.read()
        
        # 1. Parse based on file type
        if is_pdf:
            print(f"📄 Processing PDF: {file.filename}")
            parsed_data = process_pdf_to_contract(contents)
        else:
            print(f"🖼️ Processing image: {file.filename}")
            parsed_data = parse_receipt_image(contents, mime_type=file.content_type)
        
        # 2. N-Way Reconciliation
        reconciliation_result = reconcile_receipt(parsed_data)
        
        return {
            "message": f"{'PDF' if is_pdf else 'Receipt'} processed successfully",
            "file_type": "pdf" if is_pdf else "image",
            "parsed_receipt": parsed_data,
            "reconciliation": reconciliation_result
        }
        
    except ValueError as ve:
        print(f"[ingest_receipt] ValueError: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print("[ingest_receipt] Unexpected error:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
