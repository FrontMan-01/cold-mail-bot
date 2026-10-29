# Cold Mail Bot 🤖📬

An automated, lightweight cold email outreach, reply tracking, and AI draft generation pipeline built in Python with SQLite, SMTP, IMAP, and Groq Cloud. Designed to run seamlessly on Linux environments, including background daemons and low-resource systems like Raspberry Pi.

---

## 🚀 Features

- **End-to-End Lead Lifecycle**: Track prospects seamlessly from raw scraping to automated draft creation:
  $$\text{scraped} \longrightarrow \text{new} \longrightarrow \text{emailed} \longrightarrow \text{replied} \longrightarrow \text{drafted}$$
- **Outreach Automation**: Sends personalized outreach emails using standard SMTP over SSL (`smtp.gmail.com:465`) with customizable templates, attachments, and daily pacing limits.
- **RFC Thread Tracking**: Assigns and stores unique RFC `Message-ID` headers to associate threads across sessions.
- **IMAP Reply Monitoring**: Automatically scans incoming messages via IMAP (`imap.gmail.com:993`) by matching `In-Reply-To` and `References` headers, extracting plain-text response bodies (`reply_body`) while discarding HTML noise.
- **AI-Powered Draft Generation**: Generates contextual, professional reply drafts via Groq Cloud (`draft_writer.py`), guided by strict anti-hallucination and anti-placeholder directives.
- **Gmail Threaded Drafts**: Injects generated responses directly into Gmail's `[Gmail]/Drafts` folder with appropriate `In-Reply-To` and `References` headers, ready for human review before sending.
- **Prospect Discovery & Enrichment**: Includes a Selenium-based LinkedIn scraper with randomized anti-detection pacing and an interactive lead email enricher.

---

## 📁 Project Structure

```text
cold-mail-bot/
├── .env.example       # Template for required credentials and API keys
├── .gitignore         # Ignores secrets, database, virtual environment
├── companies.txt      # Input target company list (one per line)
├── db_setup.py        # Initializes the leads database schema and indexes
├── draft_writer.py    # Generates AI replies via Groq & saves Gmail drafts
├── enrich_lead.py     # Enriches 'scraped' leads with verified emails -> 'new'
├── import_leads.py    # Imports leads from CSV with duplicate detection
├── linkedin_scraper.py# Selenium LinkedIn prospect scraper with human pacing
├── mailer.py          # Sends outreach emails to 'new' leads via SMTP
├── pyrightconfig.json # Pyright/Pylance virtual environment configuration
├── reply_tracker.py   # Monitors IMAP for replies, extracts text -> 'replied'
├── report.py          # Displays pipeline statistics and conversion rates
├── requirements.txt   # Python project dependencies
├── seed.py            # Seeds test leads into the database
├── template.txt       # Cold email subject & body template with placeholders
└── view.py            # Formatted terminal viewer for all leads in the database
```

---

## 🛠️ Setup & Installation

### 1. Set Up Virtual Environment

```bash
cd cold-mail-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Credentials

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and supply your credentials:
```env
# Outreach Mailer Credentials (Gmail SMTP & IMAP)
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_APP_PASSWORD=your_16_character_app_password

# Groq LLM Configuration (AI Draft Writer)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b

# LinkedIn Scraper Credentials (Optional)
LINKEDIN_EMAIL=your.linkedin.email@example.com
LINKEDIN_PASSWORD=your_linkedin_password
```

> **Gmail App Password Note**: Generate an App Password via [Google Account Security](https://myaccount.google.com/apppasswords) (requires 2-Step Verification to be enabled).
>
> **Groq Note**: Get a free API key at [Groq Console](https://console.groq.com/). Supported active text models include `qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, etc.

---

## ⚡ Workflow & Pipeline

### 1. Initialize the Database
Creates the `leads` table and performance indexes in `leads.db`:
```bash
python db_setup.py
```

### 2. Add Prospects

- **Seed a test lead**:
  ```bash
  python seed.py
  ```
- **Scrape from LinkedIn** (populates `companies.txt` first):
  ```bash
  python linkedin_scraper.py
  ```
- **Import from CSV**:
  ```bash
  python import_leads.py linkedin_leads.csv
  ```

### 3. Enrich Leads with Verified Emails
Convert `scraped` prospects to `new` leads with verified contact emails:
```bash
# Interactive mode
python enrich_lead.py

# Or direct enrichment by lead ID
python enrich_lead.py <lead_id> <verified_email@example.com>
```

### 4. Send Outreach Emails
Sends personalized outreach using `template.txt` and attaches `cv.pdf` if present:
```bash
python mailer.py
```
- Sets a unique `Message-ID` per email and stores it in `thread_id`.
- Automatically enforces daily sending limits (default 20 emails/day).
- Transitions lead status: `new` → `emailed`.

### 5. Track Incoming Replies
Scans your Gmail INBOX for replies matching sent thread IDs:
```bash
python reply_tracker.py
```
- Fetches matching messages using `(BODY.PEEK[TEXT])`.
- Decodes and extracts clean plain-text bodies, discarding HTML.
- Stores reply content in `reply_body` and updates status: `emailed` → `replied`.

### 6. Generate AI Draft Replies
Generates contextual draft responses for received replies and syncs them to Gmail:
```bash
python draft_writer.py
```
- Queries all leads with `status = 'replied'`.
- Uses Groq (`qwen/qwen3.8-27b`) with strict anti-hallucination and anti-placeholder prompting.
- Connects to Gmail IMAP, saves the draft into `[Gmail]/Drafts` with proper `In-Reply-To` and `References` headers for conversation threading.
- Transitions lead status: `replied` → `drafted`.

### 7. Inspect Leads & Reports

- **View leads table in terminal**:
  ```bash
  python view.py
  ```
- **View aggregated metrics & reply rates**:
  ```bash
  python report.py
  ```

---

## 📊 Database Schema

Table: `leads` (stored in `leads.db`)

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique lead identifier |
| `company` | TEXT | Target company name |
| `contact_email` | TEXT | Target contact email address |
| `source` | TEXT | Lead source (e.g. `LinkedIn`, `Manual`, `Seed`) |
| `status` | TEXT | Pipeline state: `scraped`, `new`, `emailed`, `replied`, `drafted` |
| `sent_at` | TEXT | Timestamp when outreach email was sent |
| `replied_at` | TEXT | Timestamp when reply was detected via IMAP |
| `thread_id` | TEXT | Outgoing RFC `Message-ID` used for thread matching |
| `reply_body` | TEXT | Extracted plain-text content of the recipient's reply |
| `draft_text` | TEXT | LLM-generated draft response |
| `notes` | TEXT | Custom notes and lead context |

---

## 🛡️ Best Practices & Safeguards

- **No Blind Sending**: AI-generated responses are saved directly to **Gmail Drafts**, giving you full editorial review before hitting send.
- **Anti-Hallucination Prompting**: The draft writer is explicitly instructed never to fabricate availability dates, hourly rates, or commitments. If a prospect asks for pricing or scheduling, it drafts an acknowledgment stating that Vishesh will follow up with specific details.
- **Pacing & Protection**:
  - `mailer.py` includes random delays between dispatches to maintain deliverability.
  - `linkedin_scraper.py` mimics human browsing patterns with jittered scrolling and throttled requests.
  - IMAP fetch queries use `.PEEK` flags (`BODY.PEEK[...]`) to prevent marking unread inbox messages as read.
