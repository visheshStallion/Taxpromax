"""Shared helpers for the FIRS export scripts (export_ereceipt.py,
export_tax_credit_admin.py): opening a browser context (local, or
Browserbase with --browserbase), clicking a "View" link that opens a PDF in
a new tab and saving it, and pulling Label: Value fields out of the PDF's
text.
"""
import re
import sys
from pathlib import Path

import pdfplumber
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

FIELD_LINE_PATTERN = re.compile(r"^(?P<label>[A-Za-z][A-Za-z0-9 /()._-]{2,40}?):\s*(?P<value>.+)$")


def add_common_args(parser, default_user_data_dir, default_output_dir="downloads"):
    parser.add_argument("--output-dir", default=default_output_dir, help="Folder to save PDFs and the Excel file into")
    parser.add_argument(
        "--user-data-dir",
        default=default_user_data_dir,
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


def open_context(playwright, args):
    """Opens a browser context (local or Browserbase per args.browserbase).

    Returns (context, session_id) -- session_id is None for a local context.
    """
    if args.browserbase:
        from browserbase_session import create_session

        session_id, connect_url, live_view_url = create_session()
        print(f"\nBrowserbase session created ({session_id}).")
        print(f"Open this link to log in yourself (username, password, and CAPTCHA if shown):\n  {live_view_url}\n")
        browser = playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context(accept_downloads=True)
        return context, session_id

    context = playwright.chromium.launch_persistent_context(
        args.user_data_dir,
        headless=False,
        accept_downloads=True,
    )
    print("\nA browser window has opened.")
    print("Log in yourself (username, password, and CAPTCHA if shown).")
    return context, None


def close_context(context, session_id):
    context.close()
    if session_id:
        from browserbase_session import end_session

        end_session(session_id)


def fetch_pdf_via_view_link(context, page, view_link_selector, pdf_path, record_label):
    """Click a "View" link that opens a PDF in a new tab, and save it to pdf_path.

    Exits the program with a clear message if the click doesn't result in a
    download -- e.g. the PDF renders in an in-page viewer instead, which
    needs a different handling approach once seen.
    """
    with context.expect_page() as new_page_info:
        page.click(view_link_selector)
    pdf_page = new_page_info.value
    pdf_page.wait_for_load_state()

    try:
        with pdf_page.expect_download(timeout=10000) as download_info:
            pass
        download_info.value.save_as(pdf_path)
    except PlaywrightTimeoutError:
        sys.exit(
            f"{record_label}: the 'View' link didn't trigger a download. "
            "It's likely rendering the PDF in-page instead -- tell me what "
            "the resulting page/URL looks like so I can adjust this."
        )
    finally:
        pdf_page.close()


def extract_pdf_fields(pdf_path: Path):
    """Pull out (label, value) pairs plus the raw text, from a PDF.

    This assumes the PDF has selectable text (not a scanned image). If a
    document comes back as a scan, this will return no fields and an empty
    `raw_text` too -- that means OCR would be needed, which isn't wired up
    here yet.
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


def write_xlsx(rows, all_labels, sheet_title, xlsx_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(all_labels)
    for row in rows:
        ws.append([row.get(label, "") for label in all_labels])
    wb.save(xlsx_path)
