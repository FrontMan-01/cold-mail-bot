import argparse
import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")


def import_leads(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at '{csv_path}'")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at '{DB_PATH}'. Run db_setup.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted_count = 0
    skipped_count = 0

    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Normalize field names to lowercase stripped strings
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

        required_fields = {"company", "contact_email", "source"}
        if not reader.fieldnames or not required_fields.issubset(set(reader.fieldnames)):
            print(f"Error: CSV file must contain columns: company, contact_email, source (optional: notes).")
            print(f"Found headers: {reader.fieldnames}")
            conn.close()
            sys.exit(1)

        for row_idx, row in enumerate(reader, start=2):
            company = (row.get("company") or "").strip()
            contact_email = (row.get("contact_email") or "").strip()
            source = (row.get("source") or "").strip()
            notes = (row.get("notes") or "").strip() or None

            if not contact_email:
                print(f"Row {row_idx}: Skipped (empty contact_email).")
                skipped_count += 1
                continue

            # Check if contact_email already exists in leads table
            cursor.execute("SELECT 1 FROM leads WHERE contact_email = ?", (contact_email,))
            existing = cursor.fetchone()

            if existing:
                print(f"Skipped duplicate lead ({contact_email})")
                skipped_count += 1
                continue

            # Insert new lead
            cursor.execute(
                """
                INSERT INTO leads (company, contact_email, source, status, sent_at, replied_at, thread_id, notes)
                VALUES (?, ?, ?, 'new', NULL, NULL, NULL, ?)
                """,
                (company, contact_email, source, notes),
            )
            inserted_count += 1
            print(f"Inserted lead: {company} ({contact_email})")

    conn.commit()
    conn.close()

    print("\n--- Import Summary ---")
    print(f"Inserted: {inserted_count}")
    print(f"Skipped:  {skipped_count}")


def main():
    parser = argparse.ArgumentParser(description="Import leads from a CSV file into leads.db")
    parser.add_argument("csv_file", help="Path to the CSV file to import")
    args = parser.parse_args()

    import_leads(args.csv_file)


if __name__ == "__main__":
    main()
