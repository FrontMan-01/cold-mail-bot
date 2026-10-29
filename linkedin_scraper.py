"""
LinkedIn Lead Scraper for Cold Mail Bot
=======================================
Automates target prospect discovery on LinkedIn using Selenium Chrome WebDriver.
Extracts prospect names and job titles for target companies specified in companies.txt,
enforces anti-automation rate-limiting (5-15s jitter), respects a 10-lead per-company cap
and a 100-lead overall run cap, and exports structured results to linkedin_leads.csv.
"""

import argparse
import csv
import os
import random
import sys
import time
import urllib.parse

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
COMPANIES_PATH = os.path.join(BASE_DIR, "companies.txt")
OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "linkedin_leads.csv")

# Constants & Thresholds
MAX_PER_COMPANY = 10
MAX_TOTAL_PEOPLE = 100
MIN_DELAY = 5.0
MAX_DELAY = 15.0

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

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "").strip()
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "").strip()

# Import Selenium with friendly diagnostic
try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        NoSuchElementException,
        TimeoutException,
        WebDriverException,
    )
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    print("[Error] 'selenium' library is required to run this scraper.")
    print("Please install required dependencies:")
    print("  pip install -r requirements.txt")
    print("Or: pip install selenium python-dotenv")
    sys.exit(1)


def random_sleep(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY, action_desc=""):
    """Sleeps for a random duration between min_seconds and max_seconds with logging."""
    delay = round(random.uniform(min_seconds, max_seconds), 2)
    if action_desc:
        print(f"  [Pacing] Waiting {delay}s {action_desc}...")
    else:
        print(f"  [Pacing] Waiting {delay}s...")
    time.sleep(delay)


def build_chrome_driver(headless=False):
    """
    Initializes a stealth-configured Chrome WebDriver instance with anti-detection flags.
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")

    # Anti-fingerprinting and stability flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print(f"[Error] Failed to initialize ChromeDriver: {e}")
        print("Please ensure google-chrome is installed and selenium has driver access.")
        sys.exit(1)

    # Evade webdriver attribute detection in JavaScript
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def load_target_companies(file_path=COMPANIES_PATH):
    """Reads companies from a line-delimited text file, ignoring empty lines and comments."""
    if not os.path.exists(file_path):
        print(f"[Error] Companies file not found at '{file_path}'.")
        print("Please create companies.txt with one company name per line.")
        return []

    companies = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                companies.append(cleaned)

    return companies


def check_security_checkpoint(driver):
    """Detects if LinkedIn presented a verification checkpoint or CAPTCHA."""
    current_url = driver.current_url.lower()
    if "checkpoint" in current_url or "challenge" in current_url or "captcha" in current_url:
        print("\n" + "!" * 70)
        print("[ALERT] LinkedIn Security Checkpoint / CAPTCHA detected!")
        print("LinkedIn has requested manual verification (e.g. puzzle or email pin).")
        print("Please resolve the prompt in the open browser window.")
        print("The scraper will wait up to 90 seconds for you to complete it...")
        print("!" * 70 + "\n")
        
        # Wait up to 90s for user to solve challenge
        for _ in range(18):
            time.sleep(5)
            if "feed" in driver.current_url.lower() or "search" in driver.current_url.lower():
                print("[Success] Checkpoint passed. Resuming automated workflow.")
                return True
        return False
    return True


def login_linkedin(driver, email, password):
    """Logs into LinkedIn using credentials provided via environment variables."""
    print("\n[Auth] Navigating to LinkedIn login page...")
    driver.get("https://www.linkedin.com/login")
    random_sleep(3, 5, "after loading login page")

    # Check if already authenticated
    if "feed" in driver.current_url.lower():
        print("[Auth] Already logged in (active session detected).")
        return True

    wait = WebDriverWait(driver, 15)

    try:
        # Locate input fields
        username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        password_field = driver.find_element(By.ID, "password")

        # Type credentials with human-like rhythm
        print(f"[Auth] Entering credentials for account: {email}")
        for char in email:
            username_field.send_keys(char)
            time.sleep(random.uniform(0.04, 0.12))

        random_sleep(1.0, 2.0, "before entering password")

        for char in password:
            password_field.send_keys(char)
            time.sleep(random.uniform(0.04, 0.12))

        random_sleep(1.0, 2.5, "before submitting login")
        password_field.send_keys(Keys.RETURN)

        # Wait for either feed navigation or security checkpoint
        random_sleep(5, 8, "waiting for authentication response")

        if not check_security_checkpoint(driver):
            print("[Error] Security checkpoint could not be completed.")
            return False

        if "feed" in driver.current_url.lower() or "mynetwork" in driver.current_url.lower():
            print("[Auth] Successfully authenticated with LinkedIn.")
            return True

        # Check for invalid credentials banner
        error_elements = driver.find_elements(By.CSS_SELECTOR, "#error-for-username, #error-for-password, .alert-content")
        if error_elements:
            print(f"[Error] Login failed: {error_elements[0].text.strip()}")
            return False

        # If URL changed away from login, treat as success
        if "login" not in driver.current_url.lower():
            print("[Auth] Login succeeded.")
            return True

        print("[Warning] Login status unclear, proceeding with caution.")
        return True

    except TimeoutException:
        print("[Error] Timed out waiting for login form elements.")
        return False
    except Exception as e:
        print(f"[Error] Unexpected exception during login: {e}")
        return False


def clean_person_name(raw_name):
    """Cleans up raw LinkedIn member name text, stripping status badges and prefixes."""
    if not raw_name:
        return ""
    # Strip member connection badges and artifacts (e.g., '• 1st', '• 2nd', '• 3rd+')
    lines = [line.strip() for line in raw_name.split("\n") if line.strip()]
    if not lines:
        return ""
    name = lines[0]
    for badge in [" • 1st", " • 2nd", " • 3rd+", " 1st", " 2nd", " 3rd+"]:
        if name.endswith(badge):
            name = name[: -len(badge)].strip()
    return name


def scrape_people_for_company(driver, company, current_total_leads, max_total_limit=MAX_TOTAL_PEOPLE):
    """
    Searches LinkedIn for people at the specified company and extracts up to MAX_PER_COMPANY leads.
    Returns list of dicts: [{'company': ..., 'contact_name': ..., 'job_title': ..., 'source': 'LinkedIn', 'contact_email': ''}]
    """
    print(f"\n{'='*60}")
    print(f"🔍 Searching prospects for company: '{company}'")
    print(f"{'='*60}")

    encoded_query = urllib.parse.quote(company)
    search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"

    driver.get(search_url)
    random_sleep(MIN_DELAY, MAX_DELAY, "after loading search results")

    if not check_security_checkpoint(driver):
        print(f"[Warning] Security checkpoint triggered during search for '{company}'.")
        return []

    # Slowly scroll down to trigger lazy loading of search result cards
    for scroll_step in range(1, 4):
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_step / 3});")
        time.sleep(random.uniform(1.2, 2.0))

    collected_leads = []
    seen_names = set()

    # Multi-strategy result container extraction
    card_selectors = [
        "li.reusable-search__result-container",
        "div.search-results-container li",
        "div[data-view-name='search-entity-result-universal-template']",
    ]

    result_cards = []
    for selector in card_selectors:
        cards = driver.find_elements(By.CSS_SELECTOR, selector)
        if cards:
            result_cards = cards
            break

    if not result_cards:
        print(f"  [Info] No search result cards found for '{company}'.")
        return collected_leads

    print(f"  [Found] {len(result_cards)} result card(s) on current page. Parsing candidates...")

    for card in result_cards:
        # Check per-company limit
        if len(collected_leads) >= MAX_PER_COMPANY:
            print(f"  [Limit] Reached maximum quota of {MAX_PER_COMPANY} leads for '{company}'.")
            break

        # Check total run limit
        if (current_total_leads + len(collected_leads)) >= max_total_limit:
            break

        try:
            # 1. Extract Name
            name = ""
            name_selectors = [
                ".entity-result__title-text a span[aria-hidden='true']",
                ".entity-result__title-text a",
                ".app-aware-link span[aria-hidden='true']",
                "span.entity-result__title-text",
            ]
            for sel in name_selectors:
                els = card.find_elements(By.CSS_SELECTOR, sel)
                if els and els[0].text.strip():
                    name = clean_person_name(els[0].text.strip())
                    if name:
                        break

            # Skip anonymous or out-of-network placeholders
            if not name or "LinkedIn Member" in name:
                continue

            # Deduplication within current company
            if name.lower() in seen_names:
                continue

            # 2. Extract Job Title / Headline
            headline = ""
            headline_selectors = [
                ".entity-result__primary-subtitle",
                "div.linked-area .entity-result__primary-subtitle",
                "div[class*='primary-subtitle']",
            ]
            for sel in headline_selectors:
                els = card.find_elements(By.CSS_SELECTOR, sel)
                if els and els[0].text.strip():
                    headline = els[0].text.strip().replace("\n", " ")
                    break

            # Fallback if primary subtitle is empty
            if not headline:
                headline = f"Professional at {company}"

            lead_entry = {
                "company": company,
                "contact_name": name,
                "job_title": headline,
                "source": "LinkedIn",
                "contact_email": "",
            }

            collected_leads.append(lead_entry)
            seen_names.add(name.lower())
            print(f"  [+] #{len(collected_leads)}: {name} — {headline}")

        except Exception as err:
            # Skip unparseable cards gracefully
            continue

    return collected_leads


def write_leads_to_csv(leads, output_path=OUTPUT_CSV_PATH):
    """
    Appends or creates linkedin_leads.csv with the required schema:
    company, contact_name, job_title, source, contact_email
    """
    file_exists = os.path.exists(output_path)
    fieldnames = ["company", "contact_name", "job_title", "source", "contact_email"]

    with open(output_path, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for lead in leads:
            writer.writerow(lead)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Lead Scraper for Cold Mail Bot")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome in headless mode (recommended for servers and Raspberry Pi)",
    )
    args = parser.parse_args()

    # Automatically enable headless if no display server is detected (headless Linux environment)
    auto_headless = not bool(os.getenv("DISPLAY"))
    use_headless = args.headless or auto_headless

    print("=" * 70)
    print("   🤖 Cold Mail Bot — LinkedIn Prospect Scraper (Agency Council)")
    print("=" * 70)
    if use_headless:
        print("[Browser Mode] Running Chrome in HEADLESS mode.")
    else:
        print("[Browser Mode] Running Chrome in GUI window mode.")

    # 1. Credentials Validation
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        print("\n[Configuration Error] LinkedIn credentials not configured!")
        print("Please configure LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file:")
        print(f"Path: {ENV_PATH}")
        print("\nExample:")
        print("  LINKEDIN_EMAIL=your.email@example.com")
        print("  LINKEDIN_PASSWORD=your_secure_password")
        sys.exit(1)

    # 2. Load Target Companies
    companies = load_target_companies(COMPANIES_PATH)
    if not companies:
        print(f"\n[Empty Input] No target companies found in '{COMPANIES_PATH}'.")
        print("Add companies to this file (one per line) and re-run.")
        sys.exit(1)

    print(f"\n[Targets] Loaded {len(companies)} target company/companies:")
    for idx, c in enumerate(companies, start=1):
        print(f"  {idx}. {c}")

    # 3. Setup WebDriver
    print("\n[Browser] Launching Chrome WebDriver...")
    driver = build_chrome_driver(headless=use_headless)

    total_leads_collected = 0
    company_summary = {}
    limit_reached = False

    try:
        # 4. Authenticate
        logged_in = login_linkedin(driver, LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        if not logged_in:
            print("[Fatal] Could not authenticate with LinkedIn. Aborting scraper.")
            driver.quit()
            sys.exit(1)

        # 5. Process Each Company
        for c_idx, company in enumerate(companies, start=1):
            if total_leads_collected >= MAX_TOTAL_PEOPLE:
                limit_reached = True
                break

            leads = scrape_people_for_company(
                driver=driver,
                company=company,
                current_total_leads=total_leads_collected,
                max_total_limit=MAX_TOTAL_PEOPLE,
            )

            # Persist batch immediately to prevent data loss on unexpected interruption
            if leads:
                write_leads_to_csv(leads, OUTPUT_CSV_PATH)
                total_leads_collected += len(leads)
                company_summary[company] = len(leads)
            else:
                company_summary[company] = 0

            print(f"  --> Saved {len(leads)} lead(s) for '{company}' (Total: {total_leads_collected}/{MAX_TOTAL_PEOPLE})")

            # Check hard ceiling
            if total_leads_collected >= MAX_TOTAL_PEOPLE:
                limit_reached = True
                break

            # Pacing between companies
            if c_idx < len(companies):
                random_sleep(MIN_DELAY, MAX_DELAY, f"before searching next company ({c_idx}/{len(companies)})")

    except KeyboardInterrupt:
        print("\n[Interrupted] Execution aborted by user. Preserving collected leads.")
    except Exception as e:
        print(f"\n[Error] Unexpected runtime error: {e}")
    finally:
        print("\n[Browser] Closing Chrome WebDriver...")
        try:
            driver.quit()
        except Exception:
            pass

    # 6. Hard Limit Warning
    if limit_reached or total_leads_collected >= MAX_TOTAL_PEOPLE:
        print("\n" + "!" * 70)
        print("⚠️  [WARNING] HARD LIMIT REACHED: 100 TOTAL LEADS PROCESSED.")
        print("Stopping scraper run to comply with LinkedIn automation limits & safety caps.")
        print("!" * 70)

    # 7. Final Summary Report
    print("\n" + "=" * 55)
    print("           SCRAPER EXECUTION SUMMARY             ")
    print("=" * 55)
    print(f"{'Company':<30} | {'Leads Found':>12}")
    print("-" * 55)
    for comp, count in company_summary.items():
        print(f"{comp:<30} | {count:>12}")
    print("-" * 55)
    print(f"{'TOTAL PROSPECTS COLLECTED':<30} | {total_leads_collected:>12}")
    print(f"Output File: {OUTPUT_CSV_PATH}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
