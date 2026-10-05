import os
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from email.utils import make_msgid
from dotenv import load_dotenv

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

load_dotenv(ENV_PATH)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()

def run_mailer(delay_seconds=5):
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
        msg = EmailMessage()
        msg["Subject"] = f"Quick question for {company}"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = contact_email
        msg_id = make_msgid()
        msg["Message-ID"] = msg_id

        msg.set_content(
            f"Hi {company} team,\n\n"
            f"This is an automated test outreach email.\n\n"
            f"Best regards,\nVishesh"
        )

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
