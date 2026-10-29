import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def seed():
    test_leads = [
        (
            "Acme Corp",
            "Vishesh.30333@gmail.com",
            "LinkedIn",
            "new",
            None,
            None,
            None,
            "Initial test lead"
        )
    ]

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.executemany("""
        INSERT INTO leads (company, contact_email, source, status, sent_at, replied_at, thread_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, test_leads)
        conn.commit()
        inserted_count = cursor.rowcount

    print(f"Successfully seeded {inserted_count} lead(s) into leads.db.")

if __name__ == "__main__":
    seed()
