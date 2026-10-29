import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            contact_email TEXT,
            source TEXT,
            status TEXT DEFAULT 'new',
            sent_at TEXT,
            replied_at TEXT,
            thread_id TEXT,
            notes TEXT
        )
        """)

        # Performance indexes for lookups and reply tracking
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_contact_email ON leads (contact_email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_thread_id ON leads (thread_id)")

        conn.commit()

    print(f"Database, table, and indexes ready: {DB_PATH}")

if __name__ == "__main__":
    init_db()
