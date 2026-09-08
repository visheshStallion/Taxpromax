# FIRS TaxProMax Data Downloader

Semi-automated downloader for your own FIRS TaxProMax records, filtered by
date range.

**How it works:** the script opens a real, visible browser window and pauses.
*You* log in by hand -- username, password, and any CAPTCHA challenge. Your
credentials are never typed, stored, or transmitted by this script; they only
ever go through the real login form, from your own hands. Once you confirm
you're logged in, the script takes over the repetitive part: setting the date
filter and downloading the resulting file.

## Why it works this way

TaxProMax sits behind bot-detection (a CAPTCHA challenge page). Automating
past that isn't something this tool does, by design -- so login stays manual,
and only the post-login data-fetching is automated.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python download_data.py --start-date 2026-01-01 --end-date 2026-06-30
```

Downloaded files land in `./downloads` by default (`--output-dir` to change
it). Your browser session is cached in `./.browser-profile` (`--user-data-dir`
to change it) so you may not have to log in fresh every run -- delete that
folder to force a clean login.

## Finding the real selectors

`download_data.py` currently has **placeholder** selectors for the dashboard,
date filters, and download button (search for `TODO(selectors)`), since the
authenticated dashboard hasn't been inspected yet. To fill them in:

1. Run the script once, log in manually, and let it pause.
2. In the same browser window, open DevTools and inspect the actual
   date-range filter inputs and the export/download button on whatever page
   holds your records (returns, receipts, assessments, etc.).
3. Replace `RECORDS_URL`, `LOGGED_IN_MARKER_SELECTOR`,
   `START_DATE_INPUT_SELECTOR`, `END_DATE_INPUT_SELECTOR`,
   `APPLY_FILTER_BUTTON_SELECTOR`, and `DOWNLOAD_BUTTON_SELECTOR` at the top
   of `download_data.py` with the real values.

If the dashboard exposes more than one kind of record (e.g. filed returns vs.
payment receipts) with different filter/export UI, you'll likely want one
`RECORDS_URL` + selector set per record type -- ask for a second variant once
you know what's there.

## Security notes

- Never commit `.browser-profile/` or `downloads/` -- both are already in
  `.gitignore` since they can contain session cookies or your tax data.
- This script only automates your own authenticated session in your own
  browser. It does not store credentials anywhere.
