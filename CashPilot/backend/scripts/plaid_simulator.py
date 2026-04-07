import os
import sys
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db_connection

def generate_simulator_data():
    """
    Realistic small-business Plaid simulator.
    
    Generates a cash flow history that a real small business would face:
    - Tight margins (rent, payroll, SaaS eat most of the balance)
    - Late-paying clients (30-40% of invoices arrive late)
    - Surprise expenses (equipment failures, tax adjustments)
    - Seasonal revenue dips
    - A realistic mix of paid and still-pending obligations
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database. Cannot run simulator.")
        return
    cur = conn.cursor()
    
    try:
        print("Fetching entities for simulation...")
        cur.execute("SELECT id, name, entity_type, ontology_tier, goodwill_score FROM entities;")
        all_entities = cur.fetchall()
        
        vendors = [e for e in all_entities if e['entity_type'] == 'VENDOR']
        clients = [e for e in all_entities if e['entity_type'] == 'CLIENT']
        tier0 = [v for v in vendors if v['ontology_tier'] == 0]   # IRS, Payroll
        tier1 = [v for v in vendors if v['ontology_tier'] == 1]   # Credit cards
        tier2 = [v for v in vendors if v['ontology_tier'] == 2]   # Suppliers  
        tier3 = [v for v in vendors if v['ontology_tier'] == 3]   # SaaS
        
        if not vendors and not clients:
            print("No entities found. Please run seed_data.py first.")
            return

        today = datetime.now().date()

        # ──────────────────────────────────────────────
        # PHASE 1: Historical transactions (-45 days → today)
        # Simulates a realistic operating history
        # ──────────────────────────────────────────────
        print("Phase 1: Generating realistic historical cashflow (-45 days)...")
        current_date = today - timedelta(days=45)
        
        while current_date <= today:
            day_of_month = current_date.day
            
            # === RECURRING MONTHLY OBLIGATIONS ===
            if day_of_month == 1:
                # Rent / office lease (Tier 0 - locked, always due on 1st)
                if tier0:
                    entity = tier0[0]  # IRS / Payroll-like
                    cur.execute(
                        "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                        "VALUES (%s, %s, %s, 'PENDING', TRUE);",
                        (entity['id'], round(random.uniform(-2400.0, -2800.0), 2), current_date)
                    )
            
            if day_of_month == 15:
                # Payroll (Tier 0 - locked)
                if tier0 and len(tier0) > 1:
                    cur.execute(
                        "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                        "VALUES (%s, %s, %s, 'PENDING', TRUE);",
                        (tier0[1]['id'], round(random.uniform(-3200.0, -4500.0), 2), current_date)
                    )
            
            if day_of_month in [5, 20]:
                # Credit card payments (Tier 1)
                if tier1:
                    cc = random.choice(tier1)
                    cur.execute(
                        "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                        "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                        (cc['id'], round(random.uniform(-300.0, -900.0), 2), current_date)
                    )
            
            # === RANDOM VENDOR BILLS ===
            if random.random() < 0.18:
                vendor = random.choice(tier2 + tier3 if (tier2 + tier3) else vendors)
                amount = round(random.uniform(-60.0, -600.0), 2)
                due_date = current_date + timedelta(days=random.randint(7, 21))
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', %s);",
                    (vendor['id'], amount, due_date, vendor['ontology_tier'] <= 1)
                )
            
            # === SURPRISE EXPENSES (realistic failures) ===
            if random.random() < 0.04:  # ~4% chance per day = ~1-2 per month
                vendor = random.choice(vendors)
                surprise_amount = round(random.uniform(-500.0, -2000.0), 2)
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                    (vendor['id'], surprise_amount, current_date + timedelta(days=random.randint(1, 5)))
                )
            
            # === CLIENT REVENUE (irregular, sometimes late) ===
            if random.random() < 0.12:
                client = random.choice(clients)
                # Revenue varies: small daily sales vs occasional big invoices
                if random.random() < 0.3:
                    amount = round(random.uniform(1500.0, 5000.0), 2)  # Big invoice
                else:
                    amount = round(random.uniform(150.0, 800.0), 2)    # Regular sales
                
                # Clients pay late 35% of the time
                latency = random.randint(3, 12)
                if random.random() < 0.35:
                    latency += random.randint(5, 15)  # Late payment
                
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                    (client['id'], amount, current_date + timedelta(days=latency))
                )
            
            # === PROCESS PAYMENTS (clear due obligations with realistic behavior) ===
            cur.execute(
                "SELECT id, entity_id, amount, due_date FROM obligations WHERE status = 'PENDING' AND due_date <= %s;",
                (current_date,)
            )
            due_obs = cur.fetchall()
            
            for ob in due_obs:
                amount = float(ob['amount'])
                days_overdue = (current_date - ob['due_date']).days
                
                if amount < 0:  # Payable
                    # Locked (Tier 0) always pays on time
                    # Others have delays
                    if days_overdue == 0:
                        pay_prob = 0.7
                    elif days_overdue <= 3:
                        pay_prob = 0.5
                    elif days_overdue <= 7:
                        pay_prob = 0.3
                    else:
                        pay_prob = 0.8  # Eventually forced to pay
                    
                    if random.random() < pay_prob:
                        cur.execute("UPDATE obligations SET status = 'PAID' WHERE id = %s;", (ob['id'],))
                        cur.execute(
                            "INSERT INTO transactions (entity_id, amount, cleared_date, source) "
                            "VALUES (%s, %s, %s, 'PLAID_SIMULATOR');",
                            (ob['entity_id'], amount, current_date)
                        )
                        # Late payments hurt goodwill
                        if days_overdue > 3:
                            cur.execute(
                                "UPDATE entities SET goodwill_score = GREATEST(0, goodwill_score - %s) WHERE id = %s;",
                                (min(days_overdue * 2, 15), ob['entity_id'])
                            )
                        elif days_overdue == 0:
                            # On-time payment improves goodwill slightly
                            cur.execute(
                                "UPDATE entities SET goodwill_score = LEAST(100, goodwill_score + 1) WHERE id = %s;",
                                (ob['entity_id'],)
                            )
                else:  # Receivable
                    # Client payments: some pay on time, some stretch it
                    if days_overdue == 0:
                        pay_prob = 0.4
                    elif days_overdue <= 5:
                        pay_prob = 0.35
                    else:
                        pay_prob = 0.5  # Eventually pays
                    
                    if random.random() < pay_prob:
                        cur.execute("UPDATE obligations SET status = 'PAID' WHERE id = %s;", (ob['id'],))
                        cur.execute(
                            "INSERT INTO transactions (entity_id, amount, cleared_date, source) "
                            "VALUES (%s, %s, %s, 'PLAID_SIMULATOR');",
                            (ob['entity_id'], amount, current_date)
                        )
                        # Successful client payment improves their goodwill
                        goodwill_boost = 2 if days_overdue == 0 else 1
                        cur.execute(
                            "UPDATE entities SET goodwill_score = LEAST(100, goodwill_score + %s) WHERE id = %s;",
                            (goodwill_boost, ob['entity_id'])
                        )
            
            current_date += timedelta(days=1)

        # ──────────────────────────────────────────────
        # PHASE 2: Future obligations (today → +30 days)
        # These are what the simulation slider processes
        # ──────────────────────────────────────────────
        print("Phase 2: Generating future obligations (Today to +30 days)...")

        acme_vendor = next((e for e in vendors if e["name"] == "Acme Supplies"), None)
        acme_client = next((e for e in clients if e["name"] == "Acme Supplies"), None)
        if acme_vendor and acme_client:
            cur.execute(
                "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                (acme_vendor["id"], -1000.0, today + timedelta(days=4))
            )
            cur.execute(
                "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                (acme_client["id"], 400.0, today + timedelta(days=6))
            )

        for day_offset in range(1, 31):
            future_date = today + timedelta(days=day_offset)
            dom = future_date.day
            
            # Recurring monthly bills
            if dom == 1 and tier0:
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', TRUE);",
                    (tier0[0]['id'], round(random.uniform(-2400.0, -2800.0), 2), future_date)
                )
            
            if dom == 15 and tier0 and len(tier0) > 1:
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', TRUE);",
                    (tier0[1]['id'], round(random.uniform(-3200.0, -4500.0), 2), future_date)
                )
            
            if dom in [5, 20] and tier1:
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                    (random.choice(tier1)['id'], round(random.uniform(-300.0, -900.0), 2), future_date)
                )
            
            # Random vendor bills (40% chance per day)
            if random.random() < 0.40:
                vendor = random.choice(tier2 + tier3 if (tier2 + tier3) else vendors)
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                    (vendor['id'], round(random.uniform(-100.0, -800.0), 2), future_date)
                )
            
            # Client receivables (25% chance per day, with some big invoices)
            if random.random() < 0.25:
                client = random.choice(clients)
                if random.random() < 0.25:
                    amount = round(random.uniform(2000.0, 5000.0), 2)  # Big
                else:
                    amount = round(random.uniform(200.0, 1200.0), 2)   # Regular
                cur.execute(
                    "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                    "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                    (client['id'], amount, future_date)
                )
            
            # Deliberate cash crunch events on specific days
            if day_offset == 8:
                # Equipment failure / emergency repair
                if vendors:
                    cur.execute(
                        "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                        "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                        (random.choice(vendors)['id'], round(random.uniform(-1800.0, -3500.0), 2), future_date)
                    )
            
            if day_offset == 18:
                # Tax adjustment surprise
                if tier0:
                    cur.execute(
                        "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                        "VALUES (%s, %s, %s, 'PENDING', TRUE);",
                        (tier0[0]['id'], round(random.uniform(-1500.0, -2500.0), 2), future_date)
                    )
            
            if day_offset == 24:
                # Major supplier invoice
                if tier2:
                    cur.execute(
                        "INSERT INTO obligations (entity_id, amount, due_date, status, is_locked) "
                        "VALUES (%s, %s, %s, 'PENDING', FALSE);",
                        (random.choice(tier2)['id'], round(random.uniform(-2000.0, -4000.0), 2), future_date)
                    )

        conn.commit()
        
        # Print diagnostic summary
        cur.execute("SELECT status, count(*) as c FROM obligations GROUP BY status;")
        print("\n=== Obligation Summary ===")
        for r in cur.fetchall():
            print(f"  {r['status']}: {r['c']}")
        
        cur.execute("SELECT count(*) as c FROM obligations WHERE status = 'PENDING' AND due_date > %s;", (today,))
        print(f"  Future pending (> today): {cur.fetchone()['c']}")
        
        cur.execute("SELECT count(*) as c FROM obligations WHERE status = 'PENDING' AND due_date <= %s;", (today,))
        print(f"  Overdue pending (<= today): {cur.fetchone()['c']}")
        
        cur.execute("SELECT name, goodwill_score FROM entities ORDER BY ontology_tier;")
        print("\n=== Goodwill Scores ===")
        for e in cur.fetchall():
            print(f"  {e['name']}: {e['goodwill_score']}")
        
        cur.execute("SELECT plaid_current_balance FROM companies LIMIT 1;")
        print(f"\n  Starting balance: ${cur.fetchone()['plaid_current_balance']}")
        print("\nSimulation complete.")
        
    except Exception as e:
        conn.rollback()
        print("Error during simulation:", e)
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    generate_simulator_data()
