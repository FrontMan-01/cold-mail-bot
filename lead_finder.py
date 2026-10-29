"""
Lead Finder for Cold Mail Bot
=============================
Fetches remote job postings from the RemoteOK API and imports new company prospects
into leads.db with status = 'scraped'. Supports optional tag filtering and skips
duplicate companies.
"""

import argparse
import os
import sqlite3
import sys
import requests

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")
API_URL = "https://remoteok.com/api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def find_leads(tag_filter=None):
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Please run db_setup.py first.")
        return

    print("Fetching remote job postings from RemoteOK API...")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching job postings from RemoteOK: {e}")
        return

    if not isinstance(data, list) or len(data) <= 1:
        print("No job postings found in RemoteOK API response.")
        return

    # Skip first element (legal/metadata notice)
    postings = data[1:]
    print(f"Retrieved {len(postings)} total posting(s) from RemoteOK.")

    filter_tag = tag_filter.strip().lower() if tag_filter else None
    if filter_tag:
        print(f"Filtering postings with tag: '{filter_tag}'...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    added_count = 0
    skipped_duplicates = 0
    skipped_tag = 0
    seen_in_run = set()

    for item in postings:
        if not isinstance(item, dict):
            continue

        company = (item.get("company") or "").strip()
        if not company:
            continue

        # Optional tag filtering (case-insensitive)
        tags = [str(t).lower() for t in (item.get("tags") or []) if t]
        if filter_tag and filter_tag not in tags:
            skipped_tag += 1
            continue

        company_lower = company.lower()
        if company_lower in seen_in_run:
            skipped_duplicates += 1
            continue

        # Check if lead with company name already exists in leads.db (case-insensitive)
        cursor.execute("SELECT 1 FROM leads WHERE LOWER(company) = LOWER(?) LIMIT 1", (company,))
        if cursor.fetchone():
            skipped_duplicates += 1
            seen_in_run.add(company_lower)
            continue

        seen_in_run.add(company_lower)

        position = (item.get("position") or "").strip()
        url = (item.get("url") or item.get("apply_url") or "").strip()

        notes_parts = []
        if position:
            notes_parts.append(position)
        if url:
            notes_parts.append(url)
        notes = " | ".join(notes_parts) if notes_parts else None

        cursor.execute(
            """
            INSERT INTO leads (company, contact_email, source, status, sent_at, replied_at, thread_id, notes)
            VALUES (?, NULL, 'RemoteOK', 'scraped', NULL, NULL, NULL, ?)
            """,
            (company, notes),
        )
        added_count += 1

    conn.commit()
    conn.close()

    print("\n" + "=" * 45)
    print("         LEAD FINDER SUMMARY         ")
    print("=" * 45)
    if filter_tag:
        print(f"Tag filter:          {filter_tag}")
    print(f"New leads added:     {added_count}")
    print(f"Duplicates skipped:  {skipped_duplicates}")
    if filter_tag:
        print(f"Filtered out by tag: {skipped_tag}")
    print("=" * 45)


def main():
    parser = argparse.ArgumentParser(
        description="Find prospective client/employer leads from RemoteOK job postings."
    )
    parser.add_argument(
        "tag",
        nargs="?",
        default=None,
        help="Optional tag filter (e.g. python, react, dev, engineer)",
    )
    args = parser.parse_args()
    find_leads(tag_filter=args.tag)


if __name__ == "__main__":
    main()
