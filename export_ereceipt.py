#!/usr/bin/env python3
"""
FIRS e-Receipt (tcc.firs.gov.ng) PDF exporter.

Same manual-login pattern as download_data.py: a real, visible browser
window opens, you log in yourself, and only the repetitive part (opening
each receipt, grabbing its PDF, pulling out the values) is automated.

Usage:
    python export_ereceipt.py --receipt-id 2001110036357
    python export_ereceipt.py --receipt-ids-file receipt_ids.txt

`receipt_ids.txt` is a plain text file, one receipt ID per line.

Selectors marked TODO are placeholders -- the authenticated e-receipt page
hasn't been inspected yet. Fill these in after logging in once (see
README.md "Finding the real selectors").
"""
import argparse
import re
import sys
from pathlib import Path

import pdfplumber
from openpyxl import Workbook
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

LOGIN_URL = "https://tcc.firs.gov.ng/taxpayer/login"
ERECEIPT_URL_TEMPLATE = "https://tcc.firs.gov.ng/taxpayer/ereceiptTaxpayer?id={receipt_id}"

# TODO(selectors): update after inspecting the authenticated e-receipt page.
LOGGED_IN_MARKER_SELECTOR = "text=Dashboard"  # something only visible post-login
VIEW_LINK_SELECTOR = "a:has-text('View')"

# Rough "Label: Value" line pattern for parsing extracted PDF text.
# TODO: adjust once we've seen a real receipt PDF's layout -- some receipts
# use "Label ........ Value" or two-column layouts that this won't catch.
FIELD_LINE_PATTERN = re.compile(r"^(?P<label>[A-Za-z][A-Za-z0-9 /()._-]{2,40}?):\s*(?P<value>.+)$")


def parse_args():
    parser = argparse.ArgumentParser(description="Export FIRS e-Receipt PDF data to Excel.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--receipt-id", help="A single e-receipt ID, e.g. 2001110036357")
    group.add_argument("--receipt-ids-file", help="Text file with one receipt ID per line")
    parser.add_argument("--output-dir", default="downloads", help="Folder to save PDFs and the Excel file into")
    parser.add_argument("--output-xlsx", default="ereceipts.xlsx", help="Excel filename to write")
    parser.add_argument(
        "--user-data-dir",
        default=".browser-profile-tcc",
        help="Persistent browser profile folder, so your session can survive between runs (ignored with --browserbase)",
    )
    parser.add_argument(
        "--browserbase",
        action="store_true",
        help=(
            "Run the browser on Browserbase instead of locally (needs BROWSERBASE_API_KEY, and "
            "BROWSERBASE_PROJECT_ID if your account requires one). A live-view link is printed for "
            "you to log in and solve any CAPTCHA by hand -- same manual-login step, just remote."
        ),
    )
    return parser.parse_args()


def load_receipt_ids(args):
    if args.receipt_id:
        return [args.receipt_id]
    ids = []
    for line in Path(args.receipt_ids_file).read_text().splitlines():
        line = line.strip()
        if line:
            ids.append(line)
    if not ids:
        sys.exit(f"No receipt IDs found in {args.receipt_ids_file}")
    return ids


def extract_pdf_fields(pdf_path: Path):
    """Pull out (label, value) pairs plus the raw text, from a receipt PDF.

    This assumes the PDF has selectable text (not a scanned image). If a
    receipt comes back as a scan, this will return no fields and you'll see
    an empty `raw_text` too -- that means OCR would be needed, which isn't
    wired up here yet.
    """
    fields = {}
    raw_text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            raw_text_parts.append(text)
            for line in text.splitlines():
                match = FIELD_LINE_PATTERN.match(line.strip())
                if match:
                    fields[match.group("label").strip()] = match.group("value").strip()
    return fields, "\n".join(raw_text_parts)


def main():
    args = parse_args()
    receipt_ids = load_receipt_ids(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []  # each row: dict of {label: value}, plus receipt_id and raw_text
    all_labels = []  # preserves first-seen order across receipts

    session_id = None
    with sync_playwright() as p:
        if args.browserbase:
            from browserbase_session import create_session, end_session

            session_id, connect_url, live_view_url = create_session()
            print(f"\nBrowserbase session created ({session_id}).")
            print(f"Open this link to log in yourself (username, password, and CAPTCHA if shown):\n  {live_view_url}\n")
            browser = p.chromium.connect_over_cdp(connect_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context(accept_downloads=True)
        else:
            context = p.chromium.launch_persistent_context(
                args.user_data_dir,
                headless=False,
                accept_downloads=True,
            )
        page = context.pages[0] if context.pages else context.new_page()

        page.goto(LOGIN_URL)
        if not args.browserbase:
            print("\nA browser window has opened.")
            print("Log in yourself (username, password, and CAPTCHA if shown).")
        input("Once you're logged in, come back here and press Enter to continue...")

        try:
            page.wait_for_selector(LOGGED_IN_MARKER_SELECTOR, timeout=5000)
        except PlaywrightTimeoutError:
            print(
                f"Warning: couldn't confirm login via selector {LOGGED_IN_MARKER_SELECTOR!r}. "
                "Continuing anyway since you confirmed manually -- update this selector "
                "in export_ereceipt.py once you've inspected the real page."
            )

        for receipt_id in receipt_ids:
            print(f"Fetching receipt {receipt_id}...")
            page.goto(ERECEIPT_URL_TEMPLATE.format(receipt_id=receipt_id))

            # TODO(selectors): confirm once the real e-receipt page is known --
            # the "View" link might open the PDF in a new tab, a new window, or
            # navigate the current page directly to a PDF URL.
            with context.expect_page() as new_page_info:
                page.click(VIEW_LINK_SELECTOR)
            pdf_page = new_page_info.value
            pdf_page.wait_for_load_state()

            pdf_path = output_dir / f"ereceipt_{receipt_id}.pdf"
            # If the "View" link navigates straight to a PDF response, Playwright
            # surfaces it as a download; if it renders in an in-browser PDF
            # viewer instead, this download step won't fire and needs adjusting.
            try:
                with pdf_page.expect_download(timeout=10000) as download_info:
                    pass
                download_info.value.save_as(pdf_path)
            except PlaywrightTimeoutError:
                sys.exit(
                    f"Receipt {receipt_id}: the 'View' link didn't trigger a download. "
                    "It's likely rendering the PDF in-page instead -- tell me what "
                    "the resulting page/URL looks like so I can adjust this."
                )
            pdf_page.close()

            fields, raw_text = extract_pdf_fields(pdf_path)
            if not fields:
                print(f"  Warning: no 'Label: Value' fields found in receipt {receipt_id}'s PDF.")
            fields["Receipt ID"] = receipt_id
            fields["_raw_text"] = raw_text
            rows.append(fields)
            for label in fields:
                if label not in all_labels:
                    all_labels.append(label)

        context.close()
        if session_id:
            end_session(session_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "eReceipts"
    ws.append(all_labels)
    for row in rows:
        ws.append([row.get(label, "") for label in all_labels])

    xlsx_path = output_dir / args.output_xlsx
    wb.save(xlsx_path)
    print(f"Saved {len(rows)} receipt(s) to {xlsx_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
