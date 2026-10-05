import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def generate_report():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}. Run db_setup.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM leads")
    total_leads = cursor.fetchone()[0]

    cursor.execute("""
        SELECT status, COUNT(*) 
        FROM leads 
        GROUP BY status 
        ORDER BY COUNT(*) DESC
    """)
    status_counts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'replied'")
    replied_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leads WHERE status IN ('emailed', 'replied')")
    contacted_count = cursor.fetchone()[0]

    response_rate = (replied_count / contacted_count * 100) if contacted_count > 0 else 0.0

    print("=" * 40)
    print("        COLD MAIL BOT REPORT           ")
    print("=" * 40)
    print(f"Total Leads: {total_leads}")
    print(f"Contacted:   {contacted_count}")
    print(f"Replied:     {replied_count}")
    print(f"Reply Rate:  {response_rate:.1f}%\n")
    print("Breakdown by Status:")
    print("-" * 40)
    for status, count in status_counts:
        bar = "█" * min(20, count)
        print(f"  {status:<10} : {count:>4} {bar}")
    print("=" * 40)

    conn.close()

if __name__ == "__main__":
    generate_report()
