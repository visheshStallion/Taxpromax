#!/usr/bin/env python3
"""
FIRS TaxProMax data downloader.

Opens a real, visible browser window. You log in yourself (username,
password, and any CAPTCHA) by hand -- this script never sees or stores
your credentials. Once you confirm you're logged in, it automates the
repetitive part: setting a date-range filter and downloading the
resulting records into a local folder.

Usage:
    python download_data.py --start-date 2026-01-01 --end-date 2026-06-30

Selectors marked TODO are placeholders. TaxProMax's authenticated
dashboard structure hasn't been inspected yet -- fill these in after
logging in once and locating the real filter/export controls (see
README.md "Finding the real selectors").
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

LOGIN_URL = "https://taxpromax.firs.gov.ng/taxpayer/login"

# TODO(selectors): update after inspecting the authenticated dashboard.
RECORDS_URL = "https://taxpromax.firs.gov.ng/taxpayer/dashboard"  # placeholder
LOGGED_IN_MARKER_SELECTOR = "text=Dashboard"  # something only visible post-login
START_DATE_INPUT_SELECTOR = "input[name='startDate']"
END_DATE_INPUT_SELECTOR = "input[name='endDate']"
APPLY_FILTER_BUTTON_SELECTOR = "button:has-text('Filter')"
DOWNLOAD_BUTTON_SELECTOR = "button:has-text('Download')"


def parse_args():
    parser = argparse.ArgumentParser(description="Download FIRS TaxProMax records for a date range.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output-dir", default="downloads", help="Folder to save downloaded files into")
    parser.add_argument(
        "--user-data-dir",
        default=".browser-profile",
        help="Persistent browser profile folder, so your session can survive between runs",
    )
    args = parser.parse_args()

    for label, value in (("--start-date", args.start_date), ("--end-date", args.end_date)):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            parser.error(f"{label} must be in YYYY-MM-DD format, got {value!r}")

    return args


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # headless is intentionally not exposed as an option: a human has to
        # be able to see and interact with this window to log in and solve
        # any CAPTCHA challenge.
        context = p.chromium.launch_persistent_context(
            args.user_data_dir,
            headless=False,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()

        page.goto(LOGIN_URL)
        print("\nA browser window has opened.")
        print("Log in yourself (username, password, and CAPTCHA if shown).")
        input("Once you're on your dashboard, come back here and press Enter to continue...")

        try:
            page.wait_for_selector(LOGGED_IN_MARKER_SELECTOR, timeout=5000)
        except PlaywrightTimeoutError:
            print(
                f"Warning: couldn't confirm login via selector {LOGGED_IN_MARKER_SELECTOR!r}. "
                "Continuing anyway since you confirmed manually -- update this selector "
                "in download_data.py once you've inspected the real dashboard."
            )

        page.goto(RECORDS_URL)

        # TODO(selectors): confirm these once the real filter UI is known.
        page.fill(START_DATE_INPUT_SELECTOR, args.start_date)
        page.fill(END_DATE_INPUT_SELECTOR, args.end_date)
        page.click(APPLY_FILTER_BUTTON_SELECTOR)
        page.wait_for_load_state("networkidle")

        print(f"Downloading records from {args.start_date} to {args.end_date}...")
        with page.expect_download() as download_info:
            page.click(DOWNLOAD_BUTTON_SELECTOR)
        download = download_info.value

        filename = f"taxpromax_{args.start_date}_to_{args.end_date}_{download.suggested_filename}"
        dest = output_dir / filename
        download.save_as(dest)
        print(f"Saved to {dest}")

        context.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
