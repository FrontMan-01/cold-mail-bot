# Cold Mail Bot 🤖📬

An automated, lightweight cold email outreach and reply tracking pipeline built in Python with SQLite, SMTP, and IMAP. Designed to run seamlessly on Linux environments, including Raspberry Pi.

---

## 🚀 Features

- **SQLite Database**: Local, zero-configuration database to track lead lifecycle (`new` → `emailed` → `replied`).
- **Automated Mailer**: Sends personalized outreach emails using standard SMTP over SSL (`smtp.gmail.com:465`).
- **Thread Tracking**: Assigns and stores unique RFC `Message-ID` headers to associate threads across sessions.
- **IMAP Reply Tracking**: Continuously monitors incoming replies via IMAP (`imap.gmail.com:993`) by matching `In-Reply-To` and `References` headers.
- **Analytics & Reporting**: Generates instant summary reports on lead conversion and response rates.

---

## 📁 Project Structure

```text
cold-mail-bot/
├── .env.example       # Template for required environment variables
├── .gitignore          # Ignores secrets, database, virtual environment
├── db_setup.py         # Initializes the leads table schema in SQLite
├── mailer.py           # Sends emails to 'new' leads and logs Message-IDs
├── reply_tracker.py    # Monitors IMAP for replies and marks them 'replied'
├── report.py           # Displays aggregated outreach metrics and response rates
├── requirements.txt    # Python project dependencies
├── seed.py             # Seeds test leads into the database
└── view.py             # Formatted terminal viewer for all leads in the database
```

---

## 🛠️ Setup & Installation

### 1. Clone & Set Up Virtual Environment

```bash
cd cold-mail-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Credentials

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and supply your credentials:
```env
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_APP_PASSWORD=your_16_char_app_password
```

> **Note**: For Gmail, generate an App Password via [Google Account Security](https://myaccount.google.com/apppasswords) with 2-Step Verification enabled.

---

## ⚡ Workflow & Usage

### 1. Initialize the Database
```bash
python db_setup.py
```

### 2. Seed Test Leads
```bash
python seed.py
```

### 3. Check Database Records
```bash
python view.py
```

### 4. Send Outreach Emails
```bash
python mailer.py
```

### 5. Check for Incoming Replies
```bash
python reply_tracker.py
```

### 6. View Pipeline Analytics
```bash
python report.py
```

---

## 📊 Database Schema

Table: `leads`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique lead identifier |
| `company` | TEXT | Company name |
| `contact_email` | TEXT | Target contact email address |
| `source` | TEXT | Lead source (e.g. LinkedIn, Job Board) |
| `status` | TEXT | Current state: `new`, `emailed`, `replied` |
| `sent_at` | TEXT | Timestamp when email was sent |
| `replied_at` | TEXT | Timestamp when reply was detected |
| `thread_id` | TEXT | Outgoing RFC `Message-ID` used for thread matching |
| `notes` | TEXT | Additional context or lead notes |
