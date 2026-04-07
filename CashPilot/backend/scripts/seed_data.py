import os
import sys

from psycopg2 import errors

# Ensure backend acts as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db_connection


def _clear_existing_data(cur):
    print("Clearing existing data...")
    try:
        cur.execute("TRUNCATE TABLE companies CASCADE;")
    except errors.QueryCanceled:
        print("TRUNCATE timed out waiting on a table lock. Falling back to row deletes...")
        cur.execute("DELETE FROM action_logs;")
        cur.execute("DELETE FROM transactions;")
        cur.execute("DELETE FROM obligations;")
        cur.execute("DELETE FROM entities;")
        cur.execute("DELETE FROM companies;")


def seed_database():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database. Cannot seed data.")
        return
    cur = conn.cursor()
    
    try:
        # Fail fast if another session is holding locks on seeded tables.
        cur.execute("SET lock_timeout TO '5s';")
        cur.execute("SET statement_timeout TO '20s';")

        # Clear existing data for fresh seed
        _clear_existing_data(cur)
        
        # Insert initial user/company
        print("Inserting CashPilot HQ...")
        cur.execute(
             "INSERT INTO companies (name, plaid_current_balance) "
             "VALUES (%s, %s) RETURNING id;",
             ("CashPilot HQ", 12450.00)
        )
        company_id = cur.fetchone()['id']
        
        # Insert Ontological Matrix entities
        print("Populating Ontological Matrix...")
        entities_data = [
            # Tier 0 (Locked: Taxes/Payroll)
            (company_id, "IRS", "VENDOR", 0, 100, 0.05, 0),
            (company_id, "Gusto Payroll", "VENDOR", 0, 100, 0.02, 0),
            
            # Tier 1 (Penalty: Financial/Debt)
            (company_id, "Chase Credit Card", "VENDOR", 1, 100, 0.03, 1),
            (company_id, "Brex Capital", "VENDOR", 1, 100, 0.025, 1),
            
            # Tier 2 (Relational: Suppliers)
            (company_id, "Acme Supplies", "VENDOR", 2, 95, 0.015, 5),
            (company_id, "Dunder Mifflin", "VENDOR", 2, 90, 0.01, 7),
            
            # Tier 3 (Flexible: SaaS)
            (company_id, "AWS", "VENDOR", 3, 100, 0.00, 3),
            (company_id, "Slack", "VENDOR", 3, 100, 0.00, 5),
            (company_id, "HubSpot", "VENDOR", 3, 100, 0.00, 4),

            # Clients (Inflow Receivables)
            (company_id, "Acme Supplies", "CLIENT", 2, 98, 0.00, 4),
            (company_id, "Shopify Sales", "CLIENT", 3, 100, 0.00, 2),
            (company_id, "Stripe Payouts", "CLIENT", 3, 100, 0.00, 1),
            (company_id, "Enterprise Retainer", "CLIENT", 2, 100, 0.00, 7)
        ]
        
        cur.executemany(
            "INSERT INTO entities (company_id, name, entity_type, ontology_tier, goodwill_score, late_fee_rate, avg_latency_days) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s);",
            entities_data
        )
        
        conn.commit()
        print("Seed data successfully inserted.")
        
    except errors.QueryCanceled as e:
        conn.rollback()
        print("Seeding timed out while waiting on a database lock. Try again after closing other DB clients.")
        raise e
    except Exception as e:
        conn.rollback()
        print("Error during seeding:", e)
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_database()
