import argparse
import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")


def import_leads(csv_path, allow_empty_email=False):
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

    try:
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            # Normalize field names to lowercase stripped strings
            if reader.fieldnames:
                reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

            headers_set = set(reader.fieldnames or [])

            # Automatically allow empty emails if scraper fields are present (e.g. from linkedin_scraper.py)
            is_scraper_csv = "contact_name" in headers_set and "job_title" in headers_set
            permit_empty_email = allow_empty_email or is_scraper_csv

            required_fields = {"company", "source"}
            if not permit_empty_email:
                required_fields.add("contact_email")

            if not headers_set or not required_fields.issubset(headers_set):
                print(f"Error: CSV file must contain columns: company, source, and either contact_email or contact_name/job_title.")
                print(f"Found headers: {reader.fieldnames}")
                return

            for row_idx, row in enumerate(reader, start=2):
                company = (row.get("company") or "").strip()
                contact_email = (row.get("contact_email") or "").strip()
                source = (row.get("source") or "").strip()
                raw_notes = (row.get("notes") or "").strip()

                contact_name = (row.get("contact_name") or "").strip()
                job_title = (row.get("job_title") or "").strip()

                # Synthesize notes from contact_name and job_title if available
                notes_parts = []
                if contact_name:
                    notes_parts.append(f"Contact: {contact_name}")
                if job_title:
                    notes_parts.append(f"Title: {job_title}")
                if raw_notes:
                    notes_parts.append(raw_notes)

                notes = " | ".join(notes_parts) if notes_parts else None

                if not contact_email and not permit_empty_email:
                    print(f"Row {row_idx}: Skipped (empty contact_email). Use --allow-empty-email to import.")
                    skipped_count += 1
                    continue

                # Check duplicate
                if contact_email:
                    cursor.execute("SELECT 1 FROM leads WHERE contact_email = ?", (contact_email,))
                    existing = cursor.fetchone()
                else:
                    # For leads without email, check duplicate by company and synthesized notes
                    cursor.execute("SELECT 1 FROM leads WHERE company = ? AND notes = ?", (company, notes))
                    existing = cursor.fetchone()

                if existing:
                    ident = contact_email or f"{company} ({contact_name or 'No email'})"
                    print(f"Skipped duplicate lead ({ident})")
                    skipped_count += 1
                    continue

                # Leads with verified email start as 'new' (ready for mailer.py)
                # Leads without email start as 'scraped' (ready for enrichment)
                lead_status = "new" if contact_email else "scraped"

                cursor.execute(
                    """
                    INSERT INTO leads (company, contact_email, source, status, sent_at, replied_at, thread_id, notes)
                    VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?)
                    """,
                    (company, contact_email or None, source, lead_status, notes),
                )
                inserted_count += 1
                display_ident = contact_email or f"{contact_name or 'Unassigned'} [Needs Email]"
                print(f"Inserted lead [{lead_status}]: {company} ({display_ident})")

        conn.commit()
    finally:
        conn.close()

    print("\n--- Import Summary ---")
    print(f"Inserted: {inserted_count}")
    print(f"Skipped:  {skipped_count}")


def main():
    parser = argparse.ArgumentParser(description="Import leads from a CSV file into leads.db")
    parser.add_argument("csv_file", help="Path to the CSV file to import")
    parser.add_argument(
        "--allow-empty-email",
        action="store_true",
        help="Allow importing leads without an email address (stored with status='scraped')",
    )
    args = parser.parse_args()

    import_leads(args.csv_file, allow_empty_email=args.allow_empty_email)


if __name__ == "__main__":
    main()
