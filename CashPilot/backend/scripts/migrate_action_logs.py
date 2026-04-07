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
        print("Creating action_logs table if not exists...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS action_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
            action_type VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            is_resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT now(),
            status VARCHAR(50) DEFAULT 'PENDING_USER',
            chain_of_thought JSONB,
            execution_type VARCHAR(50),
            execution_payload JSONB,
            agent_thread_id VARCHAR(255)
        );
        """)
        conn.commit()
        print("Migration for action_logs successful.")
    except Exception as e:
        conn.rollback()
        print(f"Error executing migration: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
