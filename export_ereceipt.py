#!/usr/bin/env python3
"""
FIRS e-Receipt (tcc.firs.gov.ng) PDF exporter.

Same manual-login pattern as download_data.py: a real, visible browser
window (local, or Browserbase with --browserbase) opens, you log in
yourself, and only the repetitive part (opening each receipt, grabbing its
PDF, pulling out the values) is automated.

Usage:
    python export_ereceipt.py --receipt-id 2001110036357
    python export_ereceipt.py --receipt-ids-file receipt_ids.txt

`receipt_ids.txt` is a plain text file, one receipt ID per line.

Selectors marked TODO are placeholders -- the authenticated e-receipt page
hasn't been inspected yet. Fill these in after logging in once (see
README.md "Finding the real selectors").
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from firs_common import add_common_args, close_context, extract_pdf_fields, fetch_pdf_via_view_link, open_context, write_xlsx

LOGIN_URL = "https://tcc.firs.gov.ng/taxpayer/login"
ERECEIPT_URL_TEMPLATE = "https://tcc.firs.gov.ng/taxpayer/ereceiptTaxpayer?id={receipt_id}"

# TODO(selectors): update after inspecting the authenticated e-receipt page.
LOGGED_IN_MARKER_SELECTOR = "text=Dashboard"  # something only visible post-login
VIEW_LINK_SELECTOR = "a:has-text('View')"


def parse_args():
    parser = argparse.ArgumentParser(description="Export FIRS e-Receipt PDF data to Excel.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--receipt-id", help="A single e-receipt ID, e.g. 2001110036357")
    group.add_argument("--receipt-ids-file", help="Text file with one receipt ID per line")
    parser.add_argument("--output-xlsx", default="ereceipts.xlsx", help="Excel filename to write")
    add_common_args(parser, default_user_data_dir=".browser-profile-tcc")
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


def main():
    args = parse_args()
    receipt_ids = load_receipt_ids(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []  # each row: dict of {label: value}, plus receipt_id and raw_text
    all_labels = []  # preserves first-seen order across receipts

    with sync_playwright() as p:
        context, session_id = open_context(p, args)
        page = context.pages[0] if context.pages else context.new_page()

        page.goto(LOGIN_URL)
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

            pdf_path = output_dir / f"ereceipt_{receipt_id}.pdf"
            fetch_pdf_via_view_link(context, page, VIEW_LINK_SELECTOR, pdf_path, f"Receipt {receipt_id}")

            fields, raw_text = extract_pdf_fields(pdf_path)
            if not fields:
                print(f"  Warning: no 'Label: Value' fields found in receipt {receipt_id}'s PDF.")
            fields["Receipt ID"] = receipt_id
            fields["_raw_text"] = raw_text
            rows.append(fields)
            for label in fields:
                if label not in all_labels:
                    all_labels.append(label)

        close_context(context, session_id)

    xlsx_path = output_dir / args.output_xlsx
    write_xlsx(rows, all_labels, "eReceipts", xlsx_path)
    print(f"Saved {len(rows)} receipt(s) to {xlsx_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
