import os
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db import get_db_connection
from scripts.run_all import run_all

def setup_and_test():
    # 1. Run all existing scripts to prove they work
    run_all()
    
    # 2. Inject a known obligation matching the receipt we're about to test
    print("\n=== Injecting Expected Obligation ===")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM companies LIMIT 1;")
        comp_id = cur.fetchone()['id']
        
        cur.execute("INSERT INTO entities (company_id, name, entity_type, ontology_tier) VALUES (%s, %s, %s, %s) RETURNING id;",
                    (comp_id, "Template.net", "VENDOR", 3))
        entity_id = cur.fetchone()['id']
        
        # Insert a pending obligation for -325.00
        cur.execute("INSERT INTO obligations (entity_id, amount, due_date, status) VALUES (%s, %s, %s, %s) RETURNING id;",
                    (entity_id, -325.00, '2050-03-15', 'PENDING'))
        ob_id = cur.fetchone()['id']
        print(f"Injected PENDING obligation {ob_id} for Template.net at $-325.00")
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # 3. Create dummy receipt image that matches the user's uploaded image text
    print("\n=== Creating Dummy Receipt Image ===")
    img = Image.new('RGB', (500, 300), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    text = (
        "Template.net\n"
        "Plano, TX 75023\n"
        "Receipt #12345\n\n"
        "Date: March 15, 2050\n"
        "Items:\n"
        "Wireless Bluetooth Headphones   $100.00\n"
        "Premium Software Subscription   $150.00\n"
        "Portable Power Bank              $60.00\n"
        "Express Shipping Fee             $15.00\n\n"
        "Total Amount: $325.00"
    )
    d.text((20,20), text, fill=(0,0,0))
    img.save("dummy_receipt.jpg")
    print("Created dummy_receipt.jpg successfully.")

    # 4. Trigger the Ingestion API
    print("\n=== Triggering Ingestion API ===")
    import requests
    url = "http://localhost:8000/api/ingest/receipt"
    try:
        with open("dummy_receipt.jpg", "rb") as image_file:
            files = {"file": ("dummy_receipt.jpg", image_file, "image/jpeg")}
            response = requests.post(url, files=files)
        print(f"Status Code: {response.status_code}")
        print("Response object:")
        import json
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print("Failed to call API. Error:", e)

if __name__ == "__main__":
    setup_and_test()
