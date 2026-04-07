import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db import get_db_connection

def migrate():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return
        
    cur = conn.cursor()
    try:
        print("Adding current_simulated_date column to companies...")
        # Idempotent column addition
        cur.execute("""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='companies' AND column_name='current_simulated_date'
            ) THEN 
                ALTER TABLE companies ADD COLUMN current_simulated_date DATE DEFAULT CURRENT_DATE;
            END IF; 
        END $$;
        """)
        
        conn.commit()
        print("Migration successful! Stream 2 readiness complete.")
    except Exception as e:
        conn.rollback()
        print(f"Error executing migration: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
