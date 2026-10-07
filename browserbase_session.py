"""Minimal Browserbase REST client: create a cloud browser session and hand back
a live-view URL plus a Playwright connect URL.

Used so these scripts can run with no local Chrome install (e.g. from a cloud
session) -- Browserbase hosts the actual browser, and a human opens the
live-view URL to log in and solve any CAPTCHA by hand, exactly like the local
`launch_persistent_context` flow does. Credentials are never typed or seen by
this code; it only creates the remote session and connects to it afterward.

Requires BROWSERBASE_API_KEY in the environment. BROWSERBASE_PROJECT_ID is
read if set, but isn't required upfront -- we only ask for it if the API
actually rejects session creation for lacking one (accounts with a single
project may not need it).

NOTE: written from the documented Browserbase REST API shape, but not
verified against a live call in this environment (outbound network access to
api.browserbase.com was blocked while writing this). If session creation or
the live-view URL comes back wrong, share the error/response and these calls
can be adjusted.
"""
import json
import os
import sys
import urllib.request

API_BASE = "https://api.browserbase.com/v1"


def _api_key():
    key = os.environ.get("BROWSERBASE_API_KEY")
    if not key:
        sys.exit("BROWSERBASE_API_KEY is not set. Export it before using --browserbase.")
    return key


def _request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, method=method)
    req.add_header("X-BB-API-Key", _api_key())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, (e.code, e.read().decode(errors="replace"))


def create_session():
    """Create a Browserbase session. Returns (session_id, connect_url, live_view_url)."""
    body = {"keepAlive": True}
    project_id = os.environ.get("BROWSERBASE_PROJECT_ID")
    if project_id:
        body["projectId"] = project_id

    session, err = _request("POST", "/sessions", body)
    if err:
        code, text = err
        if not project_id and code in (400, 422) and "project" in text.lower():
            sys.exit(
                "Browserbase rejected session creation without a projectId "
                f"({code}: {text}). Set BROWSERBASE_PROJECT_ID (find it at "
                "https://www.browserbase.com/settings) and try again."
            )
        sys.exit(f"Browserbase API error (POST /sessions): {code} {text}")

    session_id = session["id"]
    connect_url = session["connectUrl"]

    debug, err = _request("GET", f"/sessions/{session_id}/debug")
    if err:
        sys.exit(f"Browserbase API error (GET /sessions/{session_id}/debug): {err[0]} {err[1]}")
    live_view_url = debug.get("debuggerFullscreenUrl") or debug["debuggerUrl"]

    return session_id, connect_url, live_view_url


def end_session(session_id):
    """Best-effort: ask Browserbase to release the session. Safe to ignore failures."""
    body = {"status": "REQUEST_RELEASE"}
    project_id = os.environ.get("BROWSERBASE_PROJECT_ID")
    if project_id:
        body["projectId"] = project_id
    _request("POST", f"/sessions/{session_id}", body)
