import os
import smtplib
import sqlite3
import sys
import time
from email.message import EmailMessage
from email.utils import make_msgid
from dotenv import load_dotenv

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.txt")
ATTACHMENT_PATH = "cv.pdf"


load_dotenv(ENV_PATH)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()


def load_template(template_path=TEMPLATE_PATH):
    if not os.path.exists(template_path):
        print(f"Error: Template file not found: '{template_path}'.")
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    subject_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("Subject:"):
            subject_idx = idx
            break

    if subject_idx is None:
        print(f"Error: No line starting with 'Subject:' found in '{template_path}'.")
        sys.exit(1)

    subject_template = lines[subject_idx][len("Subject:"):].strip()
    body_template = "".join(lines[subject_idx + 1:])

    return subject_template, body_template


def run_mailer(delay_seconds=5, template_path=TEMPLATE_PATH):
    subject_template, body_template = load_template(template_path)

    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("Error: EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be configured in .env file.")
        print("See .env.example for reference.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, company, contact_email FROM leads WHERE status = 'new'")
    new_leads = cursor.fetchall()

    if not new_leads:
        print("No new leads found (status = 'new').")
        conn.close()
        return

    print(f"Found {len(new_leads)} new lead(s) to process.")

    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        print("Connected and authenticated with Gmail SMTP server.")
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as e:
        print(f"\nAuthentication failed with Gmail SMTP server ({e}).")
        print("Google rejected the login credentials (535 Bad Credentials).")
        print("\nPlease check:")
        print(" 1. Did you generate an 'App Password' (not your standard Google account password)?")
        print("    -> Go to: https://myaccount.google.com/apppasswords")
        print(" 2. Make sure 2-Step Verification is turned ON on this Google account.")
        print(" 3. If you have multiple Google accounts logged into your browser, ensure you created")
        print("    the App Password under 'vishesh.0743@gmail.com', not another profile.")
        print(" 4. Paste the 16-character code into /home/jhabba/cold-mail-bot/.env")
        conn.close()
        return
    except Exception as e:
        print(f"Failed to authenticate with SMTP: {e}")
        conn.close()
        return

    for idx, (lead_id, company, contact_email) in enumerate(new_leads, start=1):
        company_name = company or ""
        subject = subject_template.replace("{company}", company_name)
        body = body_template.replace("{company}", company_name)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = contact_email
        msg_id = make_msgid()
        msg["Message-ID"] = msg_id

        msg.set_content(body)

        attachment_file = ATTACHMENT_PATH
        if not os.path.exists(attachment_file):
            proj_file = os.path.join(os.path.dirname(__file__), attachment_file)
            if os.path.exists(proj_file):
                attachment_file = proj_file

        if os.path.exists(attachment_file):
            try:
                with open(attachment_file, "rb") as f:
                    pdf_data = f.read()
                msg.add_attachment(
                    pdf_data,
                    maintype="application",
                    subtype="pdf",
                    filename=os.path.basename(attachment_file),
                )
            except Exception as e:
                print(f"Error attaching {attachment_file}: {e}")
        else:
            warning_name = os.path.basename(ATTACHMENT_PATH) if ATTACHMENT_PATH else "cv.pdf"
            print(f"{warning_name} not found, sending without attachment")

        try:
            smtp.send_message(msg)
            print(f"[{idx}/{len(new_leads)}] Sent to {contact_email} (Message-ID: {msg_id})")

            cursor.execute(
                "UPDATE leads SET status = 'emailed', sent_at = datetime('now'), thread_id = ? WHERE id = ?",
                (msg_id, lead_id),
            )
            conn.commit()
        except Exception as e:
            print(f"Error sending email to {contact_email}: {e}")

        if idx < len(new_leads):
            print(f"Waiting {delay_seconds}s before next email...")
            time.sleep(delay_seconds)

    smtp.quit()
    conn.close()
    print("Mailer run finished.")


if __name__ == "__main__":
    run_mailer()
