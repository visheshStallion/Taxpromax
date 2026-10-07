#!/usr/bin/env python3
"""
FIRS TaxProMax "Tax Credit Admin" record exporter (taxCreditAdminTp).

Same manual-login pattern as the other scripts in this repo: a browser
window (local, or Browserbase with --browserbase) opens, you log in
yourself, and only the repetitive part (opening each record, grabbing its
PDF via the "View" link, and pulling out the values) is automated.

Usage:
    python export_tax_credit_admin.py --id 2001110040527
    python export_tax_credit_admin.py --ids-file record_ids.txt

`record_ids.txt` is a plain text file, one record ID per line.

Selectors marked TODO are placeholders -- the authenticated record page
hasn't been inspected yet. Fill these in after logging in once (see
README.md "Finding the real selectors").
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from firs_common import add_common_args, close_context, extract_pdf_fields, fetch_pdf_via_view_link, open_context, write_xlsx

LOGIN_URL = "https://taxpromax.firs.gov.ng/taxpayer/login"
RECORD_URL_TEMPLATE = "https://taxpromax.firs.gov.ng/taxpayer/taxCreditAdminTp?id={record_id}&view=1"

# TODO(selectors): update after inspecting the authenticated record page.
LOGGED_IN_MARKER_SELECTOR = "text=Dashboard"  # something only visible post-login
VIEW_LINK_SELECTOR = "a:has-text('View')"


def parse_args():
    parser = argparse.ArgumentParser(description="Export FIRS TaxProMax Tax Credit Admin records to Excel.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", help="A single record ID, e.g. 2001110040527")
    group.add_argument("--ids-file", help="Text file with one record ID per line")
    parser.add_argument("--output-xlsx", default="tax_credit_admin.xlsx", help="Excel filename to write")
    add_common_args(parser, default_user_data_dir=".browser-profile-tp")
    return parser.parse_args()


def load_record_ids(args):
    if args.id:
        return [args.id]
    ids = []
    for line in Path(args.ids_file).read_text().splitlines():
        line = line.strip()
        if line:
            ids.append(line)
    if not ids:
        sys.exit(f"No record IDs found in {args.ids_file}")
    return ids


def main():
    args = parse_args()
    record_ids = load_record_ids(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []  # each row: dict of {label: value}, plus Record ID and raw_text
    all_labels = []  # preserves first-seen order across records

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
                "in export_tax_credit_admin.py once you've inspected the real dashboard."
            )

        for record_id in record_ids:
            print(f"Fetching record {record_id}...")
            page.goto(RECORD_URL_TEMPLATE.format(record_id=record_id))

            pdf_path = output_dir / f"tax_credit_admin_{record_id}.pdf"
            fetch_pdf_via_view_link(context, page, VIEW_LINK_SELECTOR, pdf_path, f"Record {record_id}")

            fields, raw_text = extract_pdf_fields(pdf_path)
            if not fields:
                print(f"  Warning: no 'Label: Value' fields found in record {record_id}'s PDF.")
            fields["Record ID"] = record_id
            fields["_raw_text"] = raw_text
            rows.append(fields)
            for label in fields:
                if label not in all_labels:
                    all_labels.append(label)

        close_context(context, session_id)

    xlsx_path = output_dir / args.output_xlsx
    write_xlsx(rows, all_labels, "TaxCreditAdmin", xlsx_path)
    print(f"Saved {len(rows)} record(s) to {xlsx_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
