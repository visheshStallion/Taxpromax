# FIRS Data Export Tools

Semi-automated exporters for your own FIRS records:

- `download_data.py` -- TaxProMax records filtered by date range.
- `export_ereceipt.py` -- e-Receipt PDFs (tcc.firs.gov.ng), with their values
  pulled into a single Excel file.

**How it works:** each script opens a real, visible browser window and
pauses. *You* log in by hand -- username, password, and any CAPTCHA
challenge. Your credentials are never typed, stored, or transmitted by these
scripts; they only ever go through the real login form, from your own hands.
Once you confirm you're logged in, the script takes over the repetitive part
(setting a filter and downloading, or opening each receipt and reading its
PDF).

## Why it works this way

These FIRS portals sit behind bot-detection (a CAPTCHA challenge page).
Automating past that isn't something these tools do, by design -- so login
stays manual, and only the post-login data-fetching is automated.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium
```

## Usage

TaxProMax records, by date range:

```bash
python download_data.py --start-date 2026-01-01 --end-date 2026-06-30
```

e-Receipts, by ID (single, or a text file with one ID per line):

```bash
python export_ereceipt.py --receipt-id 2001110036357
python export_ereceipt.py --receipt-ids-file receipt_ids.txt
```

Downloaded files (and, for e-receipts, the resulting `ereceipts.xlsx`) land in
`./downloads` by default (`--output-dir` to change it). Each script caches its
own browser session in a separate `.browser-profile*` folder (see
`--user-data-dir`) so you may not have to log in fresh every run -- delete
that folder to force a clean login.

## Finding the real selectors

Both scripts currently have **placeholder** selectors (search for
`TODO(selectors)`), since the authenticated pages haven't been inspected yet:

- `download_data.py`: `RECORDS_URL`, `LOGGED_IN_MARKER_SELECTOR`,
  `START_DATE_INPUT_SELECTOR`, `END_DATE_INPUT_SELECTOR`,
  `APPLY_FILTER_BUTTON_SELECTOR`, `DOWNLOAD_BUTTON_SELECTOR`.
- `export_ereceipt.py`: `LOGGED_IN_MARKER_SELECTOR`, `VIEW_LINK_SELECTOR`, and
  the assumption that clicking "View" triggers a file download rather than
  opening an in-page PDF viewer.

To fill them in:

1. Run the script once, log in manually, and let it pause.
2. In the same browser window, open DevTools and inspect the actual controls
   (date-range filter inputs and export button; or the "View" link and how
   it opens the PDF).
3. Replace the placeholders at the top of the relevant script with the real
   values.

If a portal exposes more than one kind of record (e.g. filed returns vs.
payment receipts) with different filter/export UI, you'll likely want one
URL + selector set per record type -- ask for a variant once you know what's
there.

`export_ereceipt.py`'s PDF field extraction also assumes each value appears
as a `Label: Value` line of selectable text (see `FIELD_LINE_PATTERN`). If a
real receipt PDF uses a different layout (columns, dotted leaders, or is a
scanned image), that pattern will need adjusting -- share what a receipt
actually looks like once you can view one.

## Security notes

- Never commit `.browser-profile*/` or `downloads/` -- both are already in
  `.gitignore` since they can contain session cookies or your tax data.
- These scripts only automate your own authenticated session in your own
  browser. They do not store credentials anywhere.
