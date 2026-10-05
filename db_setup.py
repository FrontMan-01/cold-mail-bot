import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()
    conn.close()
    print(f"Database and table ready: {DB_PATH}")

if __name__ == "__main__":
    init_db()
