import email
from email.header import decode_header
import imaplib
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

from dotenv import load_dotenv
load_dotenv(ENV_PATH)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()

def clean_header_str(val):
    if not val:
        return ""
    return str(val).strip()

def track_replies(max_recent_check=50):
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("Error: EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be configured in .env file.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, company, contact_email, thread_id FROM leads WHERE status = 'emailed' AND thread_id IS NOT NULL")
    pending_leads = cursor.fetchall()

    if not pending_leads:
        print("No pending emailed leads waiting for replies.")
        conn.close()
        return

    print(f"Tracking replies for {len(pending_leads)} emailed lead(s)...")

    # Map thread_id -> lead tuple
    # Note: thread_id might be stored with or without angle brackets e.g. <abc@xyz>
    thread_to_lead = {}
    for lead in pending_leads:
        lead_id, company, contact_email, thread_id = lead
        tid = thread_id.strip("<> \r\n")
        thread_to_lead[tid] = lead

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        print("Connected to Gmail IMAP server.")
    except Exception as e:
        print(f"Failed to connect to IMAP: {e}")
        conn.close()
        return

    status, count_data = imap.select("INBOX", readonly=True)
    if status != "OK":
        print(f"Failed to select INBOX: {status}")
        imap.logout()
        conn.close()
        return

    total_msgs = int(count_data[0])
    start_seq = max(1, total_msgs - max_recent_check + 1)
    print(f"Scanning the latest {total_msgs - start_seq + 1} email(s) in INBOX...")

    matched_count = 0

    # Fetch headers in sequence range
    fetch_range = f"{start_seq}:{total_msgs}"
    res, msg_data = imap.fetch(fetch_range, "(BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO REFERENCES FROM SUBJECT DATE)])")

    if res == "OK":
        for item in msg_data:
            if not isinstance(item, tuple):
                continue
            
            raw_headers = item[1].decode("utf-8", errors="ignore")
            msg = email.message_from_string(raw_headers)
            
            in_reply_to = clean_header_str(msg.get("In-Reply-To", ""))
            references = clean_header_str(msg.get("References", ""))
            subject = clean_header_str(msg.get("Subject", ""))
            from_addr = clean_header_str(msg.get("From", ""))

            # Check if any pending thread_id appears in In-Reply-To or References
            for tid, lead in list(thread_to_lead.items()):
                lead_id, company, contact_email, orig_thread_id = lead
                if tid in in_reply_to or tid in references:
                    print(f"\n[MATCH FOUND] Lead #{lead_id} ({company} - {contact_email})")
                    print(f"  Subject: {subject}")
                    print(f"  From: {from_addr}")
                    print(f"  Matched Thread ID: {tid}")

                    cursor.execute(
                        "UPDATE leads SET status = 'replied', replied_at = datetime('now') WHERE id = ?",
                        (lead_id,)
                    )
                    conn.commit()
                    matched_count += 1
                    # Remove from search map so we don't duplicate
                    del thread_to_lead[tid]

    imap.logout()
    conn.close()

    print(f"\nReply tracking completed. Updated {matched_count} lead(s) to 'replied'.")

if __name__ == "__main__":
    track_replies()
