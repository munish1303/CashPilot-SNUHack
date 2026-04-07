"""
Test script for PDF processing functionality.
Run this to test the PDF parser with a sample invoice.
"""
import os
from services.pdf_processor import process_pdf_to_contract

def test_pdf_processing():
    """Test PDF processing with a sample invoice file."""
    
    # Check if sample PDF exists
    sample_pdf = "invoice_sample.pdf"
    
    if not os.path.exists(sample_pdf):
        print(f"⚠️  Sample PDF '{sample_pdf}' not found.")
        print("Please place a sample invoice PDF in the backend directory to test.")
        print("\nAlternatively, you can test via the web interface:")
        print("1. Go to http://localhost:3000/ingestion")
        print("2. Upload a PDF invoice")
        print("3. Watch it get processed and reconciled!")
        return
    
    print(f"📄 Testing PDF processor with {sample_pdf}...")
    
    try:
        # Read the PDF file
        with open(sample_pdf, 'rb') as f:
            pdf_bytes = f.read()
        
        # Process it
        result = process_pdf_to_contract(pdf_bytes)
        
        if result:
            print("\n✅ Structured Data Extracted:")
            import json
            print(json.dumps(result, indent=2))
        else:
            print("❌ Failed to extract data from PDF")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_pdf_processing()
