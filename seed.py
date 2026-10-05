import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    test_leads = [
        (
            "Acme Corp",
            "vishesh.0743@gmail.com",
            "LinkedIn",
            "new",
            None,
            None,
            None,
            "Initial test lead"
        )
    ]

    cursor.executemany("""
    INSERT INTO leads (company, contact_email, source, status, sent_at, replied_at, thread_id, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, test_leads)

    conn.commit()
    inserted_count = cursor.rowcount
    conn.close()
    print(f"Successfully seeded {inserted_count} lead(s) into leads.db.")

if __name__ == "__main__":
    seed()
