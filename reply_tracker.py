import email
from email.header import decode_header
import imaplib
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

# Load environment variables with fallback
try:
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
except ImportError:
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()

def clean_header_str(val):
    if not val:
        return ""
    return str(val).strip()

def extract_plain_text(body_bytes, raw_headers=""):
    """
    Extracts and returns plain-text content from raw email body bytes.
    If the message is multipart, only text/plain parts are extracted, skipping HTML.
    """
    if not body_bytes:
        return ""

    msg = email.message_from_bytes(body_bytes)

    # If not recognized as multipart, check if boundaries exist in body or if headers clarify
    if not msg.is_multipart():
        body_str = body_bytes.decode("utf-8", errors="ignore")
        first_line = body_str.strip().splitlines()[0] if body_str.strip() else ""
        if first_line.startswith("--"):
            boundary = first_line.lstrip("-")
            msg = email.message_from_string(f'Content-Type: multipart/mixed; boundary="{boundary}"\r\n\r\n' + body_str)
        elif raw_headers:
            full_msg = email.message_from_string(raw_headers + "\r\n\r\n" + body_str)
            if full_msg.is_multipart():
                msg = full_msg

    if msg.is_multipart():
        plain_parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        plain_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        plain_parts.append(payload.decode("utf-8", errors="ignore"))
        return "\n".join(plain_parts).strip()
    else:
        # Non-multipart message
        if msg.get_content_type() == "text/html":
            return ""
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace").strip()
            except Exception:
                return payload.decode("utf-8", errors="ignore").strip()
        elif isinstance(payload, str):
            return payload.strip()
        return body_bytes.decode("utf-8", errors="ignore").strip()

def track_replies(max_recent_check=50):
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("Error: EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be configured in .env file.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Migration check: ensure reply_body column exists
    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN reply_body TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

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
    if total_msgs == 0:
        print("Inbox is empty (0 messages). No replies to check.")
        imap.logout()
        conn.close()
        return

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

            seq_tokens = (item[0].decode("utf-8", errors="ignore") if isinstance(item[0], bytes) else str(item[0])).split()
            seq_num = seq_tokens[1] if seq_tokens and seq_tokens[0] == "*" else (seq_tokens[0] if seq_tokens else "")
            
            raw_headers = item[1].decode("utf-8", errors="ignore")
            msg = email.message_from_string(raw_headers)
            
            in_reply_to = clean_header_str(msg.get("In-Reply-To", ""))
            references = clean_header_str(msg.get("References", ""))
            subject = clean_header_str(msg.get("Subject", ""))
            from_addr = clean_header_str(msg.get("From", ""))

            # Check if any pending thread_id appears in In-Reply-To or References
            for tid, lead in list(thread_to_lead.items()):
                lead_id, company, contact_email, orig_thread_id = lead
                if not tid or len(tid) < 5:
                    continue

                sender_match = contact_email.lower() in from_addr.lower() if contact_email else False
                thread_match = tid in in_reply_to or tid in references

                if thread_match and sender_match:
                    print(f"\n[MATCH FOUND] Lead #{lead_id} ({company} - {contact_email})")
                    print(f"  Subject: {subject}")
                    print(f"  From: {from_addr}")
                    print(f"  Matched Thread ID: {tid}")

                    # Fetch full message body for this email sequence number
                    reply_body = ""
                    try:
                        b_res, b_data = imap.fetch(seq_num, "(BODY.PEEK[TEXT])")
                        if b_res == "OK" and b_data:
                            body_bytes = b""
                            for b_item in b_data:
                                if isinstance(b_item, tuple) and len(b_item) > 1:
                                    body_bytes += b_item[1] if isinstance(b_item[1], bytes) else str(b_item[1]).encode("utf-8", errors="ignore")
                            reply_body = extract_plain_text(body_bytes, raw_headers)
                    except Exception as e:
                        print(f"  Warning: Failed to fetch reply body for lead #{lead_id}: {e}")

                    cursor.execute(
                        "UPDATE leads SET status = 'replied', replied_at = datetime('now', 'localtime'), reply_body = ? WHERE id = ?",
                        (reply_body, lead_id)
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
