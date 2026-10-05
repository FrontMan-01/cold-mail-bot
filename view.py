import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def view_leads():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}. Run db_setup.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM leads")
    rows = cursor.fetchall()

    if not rows:
        print("No leads found in leads table.")
        conn.close()
        return

    headers = ["ID", "Company", "Email", "Source", "Status", "Sent At", "Replied At", "Thread ID", "Notes"]
    print("-" * 105)
    print(f"{headers[0]:<4} | {headers[1]:<15} | {headers[2]:<26} | {headers[4]:<8} | {headers[5]:<19} | {headers[7]:<18}")
    print("-" * 105)

    for row in rows:
        row_id = str(row["id"])
        company = (row["company"] or "")[:15]
        email = (row["contact_email"] or "")[:26]
        status = (row["status"] or "")[:8]
        sent_at = (row["sent_at"] or "-")[:19]
        thread_id = (row["thread_id"] or "-")[:18]
        print(f"{row_id:<4} | {company:<15} | {email:<26} | {status:<8} | {sent_at:<19} | {thread_id:<18}")

    print("-" * 105)
    print(f"Total rows: {len(rows)}")
    conn.close()

if __name__ == "__main__":
    view_leads()
