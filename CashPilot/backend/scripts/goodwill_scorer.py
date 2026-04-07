import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_db_connection

def run_vendor_goodwill_scoring():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database. Cannot run scoring.")
        return
    cur = conn.cursor()
    
    try:
        print("Running Vendor Goodwill Scoring Algorithm...")
        # Since transactions don't have an obligation_id explicitly by schema,
        # we try to match them with obligations by entity_id and amount.
        # This script simulates the analysis of historical payments vs obligations.
        
        # Find transactions and their corresponding closest obligations
        query = """
            SELECT 
                t.id AS transaction_id, 
                t.entity_id, 
                t.amount, 
                t.cleared_date, 
                o.due_date,
                o.id AS obligation_id
            FROM transactions t
            JOIN obligations o 
                ON t.entity_id = o.entity_id 
                AND t.amount = o.amount
            WHERE o.status = 'PAID'
        """
        cur.execute(query)
        matches = cur.fetchall()
        
        if not matches:
            print("No matching transactions and obligations found to score.")
            return

        # Keep track of changes to entity goodwill to apply in batch
        score_changes = {}
        processed_transactions = set()

        for match in matches:
            t_id = match['transaction_id']
            # Avoid processing the same transaction over multiple obligation matches
            # just pick the first match for simplicity in this hackathon logic
            if t_id in processed_transactions:
                continue
                
            processed_transactions.add(t_id)
            entity_id = match['entity_id']
            
            if entity_id not in score_changes:
                score_changes[entity_id] = 0
                
            if match['cleared_date'] <= match['due_date']:
                # On-time
                score_changes[entity_id] += 2
            else:
                # Late
                score_changes[entity_id] -= 15
                
        # Update entities
        for entity_id, change in score_changes.items():
            if change != 0:
                print(f"Applying score change of {change} to entity {entity_id}")
                update_query = """
                    UPDATE entities 
                    SET goodwill_score = GREATEST(0, LEAST(100, goodwill_score + %s))
                    WHERE id = %s
                """
                cur.execute(update_query, (change, entity_id))
                
        conn.commit()
        print("Vendor Goodwill Scoring complete.")
        
    except Exception as e:
        conn.rollback()
        print("Error during goodwill scoring:", e)
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_vendor_goodwill_scoring()
