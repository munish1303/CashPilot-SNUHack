import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.seed_data import seed_database
from scripts.plaid_simulator import generate_simulator_data
from scripts.goodwill_scorer import run_vendor_goodwill_scoring

def run_all():
    print("=== Phase 1: Seeding Database ===")
    seed_database()
    
    print("\n=== Phase 2: Simulating Plaid Transactions ===")
    generate_simulator_data()
    
    print("\n=== Phase 3: Vendor Goodwill Scoring ===")
    run_vendor_goodwill_scoring()
    
    print("\nAll scripts executed successfully!")

if __name__ == "__main__":
    run_all()
