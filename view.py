import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def view_leads():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}. Run db_setup.py first.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads ORDER BY id ASC")
        rows = cursor.fetchall()

    if not rows:
        print("No leads found in leads table.")
        return

    print("=" * 125)
    print(f"{'ID':<4} | {'Company':<15} | {'Contact Email':<26} | {'Source':<10} | {'Status':<9} | {'Sent At':<19} | {'Notes':<25}")
    print("=" * 125)

    for row in rows:
        row_id = str(row["id"])
        company = (row["company"] or "")[:15]
        email = (row["contact_email"] or "[No Email]")[:26]
        source = (row["source"] or "-")[:10]
        status = (row["status"] or "")[:9]
        sent_at = (row["sent_at"] or "-")[:19]
        notes = (row["notes"] or "-")[:25]
        print(f"{row_id:<4} | {company:<15} | {email:<26} | {source:<10} | {status:<9} | {sent_at:<19} | {notes:<25}")

    print("=" * 125)
    print(f"Total rows: {len(rows)}")

if __name__ == "__main__":
    view_leads()
