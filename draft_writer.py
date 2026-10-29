from email.message import EmailMessage
import imaplib
import os
import sqlite3
import sys
import time
from groq import Groq

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.txt")

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

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()


def get_original_subject(template_path=TEMPLATE_PATH):
    """
    Extracts the default subject line from template.txt if present.
    """
    if os.path.exists(template_path):
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Subject:"):
                        return line[len("Subject:"):].strip()
        except Exception:
            pass
    return "A quick introduction — Vishesh Mehta"


def draft_replies():
    # 1. Validate environment configuration
    if not GROQ_API_KEY:
        print("Error: GROQ_API_KEY must be configured in .env file.")
        return

    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("Error: EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be configured in .env file.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Migration check: ensure draft_text column exists
    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN draft_text TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # 3. Query leads waiting for drafts
    cursor.execute("""
        SELECT id, company, contact_email, thread_id, reply_body 
        FROM leads 
        WHERE status = 'replied' AND reply_body IS NOT NULL
    """)
    leads = cursor.fetchall()

    if not leads:
        print("No leads found with status = 'replied' and reply_body.")
        conn.close()
        return

    print(f"Found {len(leads)} replied lead(s) to generate drafts for.")

    # Determine default reply subject
    orig_subject = get_original_subject()
    if orig_subject:
        reply_subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
    else:
        reply_subject = "Re: Following up"

    # Initialize Groq client
    try:
        client = Groq(api_key=GROQ_API_KEY)
        print(f"Initialized Groq client (model: {GROQ_MODEL}).")
    except Exception as e:
        print(f"Failed to initialize Groq client: {e}")
        conn.close()
        return

    # 6. Connect via imaplib to Gmail
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        print("Connected to Gmail IMAP server.")
    except Exception as e:
        print(f"Failed to connect to Gmail IMAP server: {e}")
        conn.close()
        return

    # Select the [Gmail]/Drafts mailbox
    status, _ = imap.select('"[Gmail]/Drafts"')
    if status != "OK":
        status, _ = imap.select("[Gmail]/Drafts")
    if status != "OK":
        print(f"Failed to select '[Gmail]/Drafts' mailbox: {status}")
        try:
            imap.logout()
        except Exception:
            pass
        conn.close()
        return

    drafts_saved_count = 0

    for lead in leads:
        lead_id, company, contact_email, thread_id, reply_body = lead
        company_name = company or "the company"
        print(f"\nProcessing Lead #{lead_id} ({company_name} - {contact_email})...")

        # 4 & 9. Groq API call wrapped in try/except
        draft_text = None
        try:
            system_prompt = (
                "You are drafting a short, professional reply on behalf of Vishesh, "
                "a freelance developer, responding to an email from a potential client "
                "or employer. Keep it concise, friendly, and avoid overpromising. "
                "Do not use placeholder brackets like [Client Name] or [Company Name]. "
                "If you don't know the recipient's name, address them generically "
                "(e.g. 'Hi there' or skip a greeting name entirely) rather than inventing a placeholder. "
                "Never invent specific facts not present in the client's reply or explicitly provided to you — "
                "this includes dates, times, availability, rates, qualifications, or commitments. "
                "If the reply asks something you don't have information for (e.g. scheduling, availability, pricing), "
                "write the draft so it acknowledges their message and says Vishesh will follow up with those specifics, "
                "rather than fabricating an answer. "
                "Return only the body of the reply without any subject line or headers."
            )
            user_message = (
                f"Company: {company_name}\n"
                "The contact's name is unknown — do not guess or placeholder it.\n\n"
                f"Client's Reply:\n{reply_body}"
            )

            chat_completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            draft_text = chat_completion.choices[0].message.content.strip()

            # Strip leading Subject: header line if the model happens to output one
            if draft_text.lower().startswith("subject:"):
                lines = draft_text.splitlines()
                idx = 1
                while idx < len(lines) and not lines[idx].strip():
                    idx += 1
                draft_text = "\n".join(lines[idx:]).strip()
            print(f"  Generated draft response via Groq ({len(draft_text)} chars).")
        except Exception as e:
            print(f"  Error generating draft with Groq for lead #{lead_id}: {e}")
            continue

        # 5. Store generated draft_text in leads table
        try:
            cursor.execute("UPDATE leads SET draft_text = ? WHERE id = ?", (draft_text, lead_id))
            conn.commit()
        except Exception as e:
            print(f"  Warning: Failed to update draft_text for lead #{lead_id}: {e}")

        # 6, 7 & 9. IMAP append to Gmail Drafts wrapped in try/except
        try:
            msg = EmailMessage()
            msg["To"] = contact_email
            msg["From"] = EMAIL_ADDRESS
            msg["Subject"] = reply_subject

            if thread_id:
                clean_tid = thread_id.strip()
                if not clean_tid.startswith("<"):
                    clean_tid = f"<{clean_tid}>"
                msg["In-Reply-To"] = clean_tid
                msg["References"] = clean_tid

            msg.set_content(draft_text)

            # Append draft to [Gmail]/Drafts
            append_res, append_data = imap.append(
                '"[Gmail]/Drafts"',
                r'(\Draft)',
                imaplib.Time2Internaldate(time.time()),
                msg.as_bytes()
            )
            if append_res != "OK":
                append_res, append_data = imap.append(
                    "[Gmail]/Drafts",
                    r'(\Draft)',
                    imaplib.Time2Internaldate(time.time()),
                    msg.as_bytes()
                )

            if append_res != "OK":
                raise RuntimeError(f"IMAP append failed with status {append_res}: {append_data}")

            # 7. Update status to 'drafted' upon successful append
            cursor.execute("UPDATE leads SET status = 'drafted' WHERE id = ?", (lead_id,))
            conn.commit()
            print(f"  Successfully saved draft to Gmail and updated status to 'drafted'.")
            drafts_saved_count += 1
        except Exception as e:
            print(f"  Error saving draft to Gmail for lead #{lead_id}: {e}")
            continue

    # Clean up connections
    try:
        imap.logout()
    except Exception:
        pass
    conn.close()

    # 8. Print summary
    print(f"\nDrafting completed. Generated and saved {drafts_saved_count} draft(s) out of {len(leads)} lead(s).")


if __name__ == "__main__":
    draft_replies()
