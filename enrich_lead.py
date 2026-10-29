"""
Lead Email Enricher for Cold Mail Bot
=====================================
Transitions scraped prospect records (status='scraped') into actionable leads (status='new')
by attaching verified contact email addresses. Supports single ID enrichment, interactive
terminal walkthrough, and batch CSV imports.
"""

import argparse
import csv
import os
import re
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email_str):
    """Validates basic email formatting."""
    cleaned = (email_str or "").strip()
    return cleaned if EMAIL_REGEX.match(cleaned) else None


def list_unenriched_leads(cursor):
    """Fetches all leads currently lacking an email address or marked as 'scraped'."""
    cursor.execute("""
        SELECT id, company, source, status, notes 
        FROM leads 
        WHERE status = 'scraped' OR contact_email IS NULL OR contact_email = ''
        ORDER BY id ASC
    """)
    return cursor.fetchall()


def display_unenriched_leads(cursor):
    """Renders a clean terminal overview of all leads awaiting enrichment."""
    rows = list_unenriched_leads(cursor)
    if not rows:
        print("\n✨ No unenriched leads found! All leads in leads.db have verified emails.")
        return 0

    print("\n" + "=" * 90)
    print(f"{'ID':<5} | {'Company':<20} | {'Status':<10} | {'Prospect / Notes':<45}")
    print("=" * 90)
    for row in rows:
        lead_id, company, source, status, notes = row
        notes_str = (notes or "-")[:45]
        print(f"{lead_id:<5} | {company[:20]:<20} | {status:<10} | {notes_str:<45}")
    print("=" * 90)
    print(f"Total leads awaiting enrichment: {len(rows)}\n")
    return len(rows)


def enrich_single_lead(cursor, lead_id, email, quiet=False):
    """
    Enriches a single lead row by ID with the given email address.
    Transitions status: 'scraped' -> 'new'
    Returns True if successfully updated, False otherwise.
    """
    valid_email = validate_email(email)
    if not valid_email:
        if not quiet:
            print(f"[Error] Invalid email format: '{email}'")
        return False

    # Check lead existence
    cursor.execute("SELECT id, company, status, notes FROM leads WHERE id = ?", (lead_id,))
    lead = cursor.fetchone()
    if not lead:
        if not quiet:
            print(f"[Error] Lead ID #{lead_id} does not exist in leads.db.")
        return False

    _, company, old_status, notes = lead

    # Check if this email is already assigned to another lead
    cursor.execute("SELECT id, company FROM leads WHERE contact_email = ? AND id != ?", (valid_email, lead_id))
    conflict = cursor.fetchone()
    if conflict:
        conflict_id, conflict_company = conflict
        if not quiet:
            print(f"[Error] Email '{valid_email}' is already assigned to Lead #{conflict_id} ({conflict_company}).")
        return False

    # Update lead record
    cursor.execute(
        """
        UPDATE leads 
        SET contact_email = ?, status = 'new'
        WHERE id = ?
        """,
        (valid_email, lead_id),
    )

    if not quiet:
        print(f"✅ Lead #{lead_id} ({company}) enriched with '{valid_email}'. Status: '{old_status}' -> 'new'.")
    return True


def run_interactive_mode():
    """Interactive loop allowing operators to enrich leads one-by-one."""
    if not os.path.exists(DB_PATH):
        print(f"[Error] Database file not found at '{DB_PATH}'. Run db_setup.py first.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        total_waiting = display_unenriched_leads(cursor)
        if total_waiting == 0:
            return

        print("Interactive Enrichment Mode (Type 'q' or press Ctrl+C to quit)")
        print("-" * 60)

        while True:
            try:
                lead_id_input = input("Enter Lead ID to enrich (or 'q' to quit): ").strip()
                if not lead_id_input or lead_id_input.lower() in ("q", "quit", "exit"):
                    print("Exiting interactive enrichment.")
                    break

                try:
                    lead_id = int(lead_id_input)
                except ValueError:
                    print("Please enter a valid numeric Lead ID.")
                    continue

                cursor.execute("SELECT id, company, notes FROM leads WHERE id = ?", (lead_id,))
                target = cursor.fetchone()
                if not target:
                    print(f"Lead #{lead_id} not found.")
                    continue

                _, company, notes = target
                print(f"  Target: {company} | {notes or 'No details'}")
                email_input = input(f"  Enter email for {company}: ").strip()

                if not email_input:
                    print("  Skipped (empty email).")
                    continue

                success = enrich_single_lead(cursor, lead_id, email_input)
                if success:
                    conn.commit()

            except (KeyboardInterrupt, EOFError):
                print("\nEnrichment interrupted by user. Saved changes.")
                break


def run_batch_csv_mode(csv_path):
    """Enriches leads in bulk from a CSV containing (id, contact_email) or (company, contact_email)."""
    if not os.path.exists(csv_path):
        print(f"[Error] CSV file not found at '{csv_path}'.")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"[Error] Database file not found at '{DB_PATH}'.")
        sys.exit(1)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        enriched_count = 0
        skipped_count = 0

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

            for row_idx, row in enumerate(reader, start=2):
                email = (row.get("contact_email") or row.get("email") or "").strip()
                raw_id = (row.get("id") or "").strip()
                company = (row.get("company") or "").strip()

                if not email or not validate_email(email):
                    skipped_count += 1
                    continue

                lead_id = None
                if raw_id.isdigit():
                    lead_id = int(raw_id)
                elif company:
                    cursor.execute(
                        "SELECT id FROM leads WHERE company = ? AND (contact_email IS NULL OR contact_email = '') LIMIT 1",
                        (company,),
                    )
                    found = cursor.fetchone()
                    if found:
                        lead_id = found[0]

                if lead_id and enrich_single_lead(cursor, lead_id, email, quiet=True):
                    enriched_count += 1
                    print(f"Row {row_idx}: Enriched Lead #{lead_id} ({company or 'ID'}) -> {email}")
                else:
                    skipped_count += 1

        conn.commit()

    print("\n--- Batch Enrichment Summary ---")
    print(f"Enriched: {enriched_count}")
    print(f"Skipped:  {skipped_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich scraped leads with verified email addresses (status: 'scraped' -> 'new')"
    )
    parser.add_argument("lead_id", nargs="?", type=int, help="ID of the lead in leads.db to enrich")
    parser.add_argument("email", nargs="?", help="Verified contact email address")
    parser.add_argument("--list", action="store_true", help="List all leads currently waiting for email enrichment")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run guided interactive terminal enrichment")
    parser.add_argument("--csv", help="Enrich leads in batch from a CSV file (columns: id/company, contact_email)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"[Error] Database file not found at '{DB_PATH}'. Run db_setup.py first.")
        sys.exit(1)

    # 1. Direct CLI Mode: enrich_lead.py <lead_id> <email>
    if args.lead_id and args.email:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            success = enrich_single_lead(cursor, args.lead_id, args.email)
            if success:
                conn.commit()
            else:
                sys.exit(1)
        return

    # 2. Batch CSV Mode: enrich_lead.py --csv file.csv
    if args.csv:
        run_batch_csv_mode(args.csv)
        return

    # 3. List Mode: enrich_lead.py --list
    if args.list:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            display_unenriched_leads(cursor)
        return

    # 4. Default: Guided Interactive Mode
    run_interactive_mode()


if __name__ == "__main__":
    main()
