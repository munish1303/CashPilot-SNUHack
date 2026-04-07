import requests
import sys

def test_ingestion_api(image_path: str):
    url = "http://localhost:8000/api/ingest/receipt"
    
    print(f"Testing Ingestion API with image: {image_path}")
    
    try:
        with open(image_path, "rb") as image_file:
            files = {"file": (image_path, image_file, "image/jpeg")}
            response = requests.post(url, files=files)
            
        print(f"Status Code: {response.status_code}")
        try:
            print("Response JSON:")
            print(response.json())
        except Exception:
            print("Response Text:")
            print(response.text)
            
    except Exception as e:
        print(f"Error testing API: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ingestion.py <path_to_receipt_image.jpg>")
    else:
        test_ingestion_api(sys.argv[1])
