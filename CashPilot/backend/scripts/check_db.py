import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

# Check obligation status counts
cur.execute("SELECT status, count(*) as c FROM obligations GROUP BY status;")
print("=== Obligation Status Counts ===")
for r in cur.fetchall():
    print(f"  {r['status']}: {r['c']}")

# Check pending obligation date range
cur.execute("SELECT count(*) as c, min(due_date) as earliest, max(due_date) as latest FROM obligations WHERE status = 'PENDING';")
row = cur.fetchone()
print(f"\n=== Pending Obligations ===")
print(f"  Count: {row['c']}, Earliest: {row['earliest']}, Latest: {row['latest']}")

# Check company state
cur.execute("SELECT plaid_current_balance, current_simulated_date FROM companies LIMIT 1;")
company = cur.fetchone()
print(f"\n=== Company State ===")
print(f"  Balance: {company['plaid_current_balance']}, Simulated Date: {company['current_simulated_date']}")

# Sample some pending obligations
cur.execute("SELECT id, amount, due_date, is_locked FROM obligations WHERE status = 'PENDING' ORDER BY due_date LIMIT 10;")
print(f"\n=== Sample Pending Obligations ===")
for r in cur.fetchall():
    print(f"  Due: {r['due_date']}, Amount: {r['amount']}, Locked: {r['is_locked']}")

cur.close()
conn.close()
