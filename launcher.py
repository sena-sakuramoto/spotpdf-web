import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, date

import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Local Imports ---
# Use the centralized OAuth helper
from auth.google_oauth import get_creds

# --- Configuration ---
# Scopes required for this launcher
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
# The app name determines the %APPDATA% folder (e.g., %APPDATA%/SpotPDF)
APP_NAME = "SpotPDF"
CONFIG_FILE = "GoogleLoginLauncher/SpotPDFLauncher.config.json"


def load_config():
    """Loads configuration from the JSON file."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # ClientId/Secret are no longer needed here; get_creds handles it.
        required_keys = ["TargetExePath", "ServiceAccountKeyPath", "SpreadsheetUrl"]
        for key in required_keys:
            if not config.get(key):
                print(f"Error: '{key}' not found in config.", file=sys.stderr)
                return None

        if not os.path.exists(config["TargetExePath"]):
            print(f"Error: Target EXE not found at '{config.get('TargetExePath')}'", file=sys.stderr)
            return None
            
        if not os.path.exists(config["ServiceAccountKeyPath"]):
            print(f"Error: Service Account Key not found at '{config.get('ServiceAccountKeyPath')}'", file=sys.stderr)
            return None

        return config
    except FileNotFoundError:
        print(f"Error: Config file not found at '{CONFIG_FILE}'", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{CONFIG_FILE}'", file=sys.stderr)
        return None

def get_authorized_users(config):
    """Fetches the list of authorized users from the Google Sheet."""
    try:
        sa_creds = ServiceAccountCredentials.from_service_account_file(
            config["ServiceAccountKeyPath"],
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        client = gspread.authorize(sa_creds)
        spreadsheet = client.open_by_url(config["SpreadsheetUrl"])
        # Prefer named sheet 'auth' or configured name; fallback to first sheet
        sheet_name = os.getenv("SHEET_NAME") or config.get("SheetName") or "auth"
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            worksheet = spreadsheet.sheet1
        records = worksheet.get_all_records()
        
        authorized_users = {}
        for record in records:
            email = record.get('email')
            exp_date_str = record.get('expiration_date')
            if email and exp_date_str:
                try:
                    # Handles various date formats, but YYYY-MM-DD is recommended
                    exp_date = datetime.strptime(str(exp_date_str), "%Y-%m-%d").date()
                    authorized_users[email.lower()] = exp_date
                except ValueError:
                    print(f"Warning: Skipping user '{email}' due to invalid date format '{exp_date_str}'. Please use YYYY-MM-DD.", file=sys.stderr)
        return authorized_users
    except gspread.exceptions.SpreadsheetNotFound:
        print("Error: Spreadsheet not found. Check the URL and sharing settings.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error accessing spreadsheet: {e}", file=sys.stderr)
        return None

def main():
    """Main function to run the launcher."""
    # Note: This launcher does not implement single-instance locking or logging
    # like main.py. It's a separate entrypoint. For those features, run main.py.
    
    config = load_config()
    if not config:
        sys.exit(1)

    # --- Get authorized users from Google Sheet ---
    authorized_users = get_authorized_users(config)
    if authorized_users is None:
        sys.exit(1) # Error message already printed

    # --- Authenticate the user via Google Sign-In ---
    try:
        # Use the centralized helper. It will find client_secrets.json and
        # token.json in %APPDATA%/SpotPDF/
        creds = get_creds(app_name=APP_NAME, scopes=SCOPES)
        if not creds:
            print("Error: Could not obtain Google credentials.", file=sys.stderr)
            sys.exit(2)

        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()

        email = user_info.get('email')
        name = user_info.get('name', email)

        if not email or not user_info.get('verified_email'):
            print("Error: Email is not available or not verified.", file=sys.stderr)
            sys.exit(3)

        # --- Authorization Check ---
        user_email_lower = email.lower()
        if user_email_lower not in authorized_users:
            print(f"Access Denied: User '{email}' is not on the authorized list.", file=sys.stderr)
            sys.exit(4)
        
        expiration_date = authorized_users[user_email_lower]
        if expiration_date < date.today():
            print(f"Access Denied: The demo period for user '{email}' expired on {expiration_date}.", file=sys.stderr)
            sys.exit(4)

        # --- Launch Target Application ---
        target_exe = config["TargetExePath"]
        args = [target_exe, "--user-email", email, "--user-name", name]
        
        print(f"Authentication successful. Launching application for {email}...")
        
        working_dir = os.path.dirname(target_exe)
        subprocess.run(args, cwd=working_dir or None, check=True)

    except HttpError as error:
        print(f"An API error occurred: {error}", file=sys.stderr)
        sys.exit(5)
    except FileNotFoundError as e:
        # Specifically catch if client_secrets.json is missing from get_creds
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
