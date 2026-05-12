#!/usr/bin/env python3
"""
Google Drive upload tool for competitor analysis reports.
Finds or creates the target folder (from business_profile.yaml), uploads the PDF,
returns the shareable link. Works for any company profile.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

load_dotenv()

ROOT = Path(__file__).parent.parent
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token.json"


def get_drive_service(reauth: bool = False):
    creds = None

    if not reauth and TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(
                    "ERROR: credentials.json not found.\n"
                    "Download it from Google Cloud Console > APIs & Services > Credentials.\n"
                    f"Place it at: {CREDENTIALS_FILE}",
                    file=sys.stderr,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def find_or_create_folder(service, folder_name: str) -> str:
    """Return the Drive folder ID, creating it if it doesn't exist."""
    query = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
        print(f"Found existing folder '{folder_name}' (id: {folder_id})")
        return folder_id

    folder_meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=folder_meta, fields="id").execute()
    folder_id = folder["id"]
    print(f"Created new folder '{folder_name}' (id: {folder_id})")
    return folder_id


def upload_pdf(service, pdf_path: str, folder_id: str) -> dict:
    """Upload PDF to the given folder. Returns file metadata including webViewLink."""
    file_name = Path(pdf_path).name
    file_meta = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)

    print(f"Uploading {file_name}...")
    uploaded = service.files().create(
        body=file_meta,
        media_body=media,
        fields="id, name, webViewLink, webContentLink",
    ).execute()
    return uploaded


def make_shareable(service, file_id: str) -> str:
    """Set the file to 'anyone with link can view' and return the view link."""
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()
    # Fetch the link in a separate call after permission propagates
    file_data = service.files().get(
        fileId=file_id,
        fields="id, webViewLink",
        supportsAllDrives=False,
    ).execute()
    file_id = file_data.get("id", file_id)
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"


def main():
    parser = argparse.ArgumentParser(description="Upload competitor analysis PDF report to Google Drive")
    parser.add_argument("pdf_path", nargs="?", help="Path to the PDF file to upload")
    parser.add_argument(
        "--profile",
        default=str(ROOT / "business_profile.yaml"),
        help="Path to business_profile.yaml",
    )
    parser.add_argument(
        "--folder",
        default=None,
        help="Override Google Drive folder name (default: from business_profile.yaml)",
    )
    parser.add_argument(
        "--reauth",
        action="store_true",
        help="Force re-authentication with Google",
    )
    args = parser.parse_args()

    with open(args.profile) as f:
        profile = yaml.safe_load(f)

    company_name = profile.get("company", {}).get("name", "Company")
    folder_name = args.folder or profile.get("google_drive", {}).get(
        "reports_folder_name", f"{company_name} Competitor Analysis Reports"
    )

    if not args.pdf_path:
        # Find the most recent PDF in .tmp/
        tmp = ROOT / ".tmp"
        pdfs = sorted(tmp.glob("*_competitor_analysis_*.pdf"))
        if not pdfs:
            print("ERROR: No PDF found in .tmp/. Run generate_report_pdf.py first.", file=sys.stderr)
            sys.exit(1)
        pdf_path = str(pdfs[-1])
        print(f"Auto-selected PDF: {pdf_path}")
    else:
        pdf_path = args.pdf_path

    if not Path(pdf_path).exists():
        print(f"ERROR: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    try:
        service = get_drive_service(reauth=args.reauth)
        folder_id = find_or_create_folder(service, folder_name)
        uploaded = upload_pdf(service, pdf_path, folder_id)
        share_link = make_shareable(service, uploaded["id"])

        print(f"\nUpload complete!")
        print(f"  File: {uploaded['name']}")
        print(f"  Drive link: {share_link}")

        return share_link

    except HttpError as e:
        print(f"ERROR: Google Drive API error: {e}", file=sys.stderr)
        if "invalid_grant" in str(e).lower():
            print("Try re-authenticating: python tools/upload_to_drive.py --reauth", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
