#!/usr/bin/env python3
"""One-time OAuth 2.0 authorization: produces the refresh token the bot needs.

OAuth 2.0 access tokens last two hours, so the bot cannot hold one in an
environment variable. It keeps a refresh token instead and trades it for an
access token on every run. This script performs the Authorization Code Flow
with PKCE once to obtain that refresh token.

    python scripts/authorize.py --client-id ... --client-secret ...

The App must have OAuth 2.0 enabled with "Automated App or Bot" as its type
(that makes it a confidential client, which is what issues a client secret),
and http://127.0.0.1:8721/callback registered as a callback URL.
"""

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import requests

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REDIRECT_URI = "http://127.0.0.1:8721/callback"
SCOPES = "tweet.read tweet.write users.read media.write offline.access"


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    query = None

    def do_GET(self):
        CallbackHandler.query = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Authorization received. You can close this tab.")

    def log_message(self, *args):
        pass


def wait_for_callback():
    server = http.server.HTTPServer(("127.0.0.1", 8721), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout=300)
    server.server_close()
    return CallbackHandler.query


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", default=os.environ.get("CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.environ.get("CLIENT_SECRET"))
    args = parser.parse_args(argv)

    if not args.client_id or not args.client_secret:
        parser.error("--client-id and --client-secret are required")

    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    state = secrets.token_urlsafe(16)

    url = f"{AUTHORIZE_URL}?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": args.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    print("Open this URL and approve the App:\n")
    print(url, "\n")
    webbrowser.open(url)

    query = wait_for_callback()
    if not query or "code" not in query:
        print("No authorization code received.", file=sys.stderr)
        return 1
    if query.get("state", [None])[0] != state:
        print("State mismatch; aborting.", file=sys.stderr)
        return 1

    # The code expires 30 seconds after approval, so exchange it immediately.
    response = requests.post(
        TOKEN_URL,
        auth=(args.client_id, args.client_secret),
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    if not response.ok:
        print(f"Token exchange failed ({response.status_code}): {response.text}", file=sys.stderr)
        return 1

    payload = response.json()
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        print(
            "No refresh token returned. The offline.access scope is required "
            "and must be approved.",
            file=sys.stderr,
        )
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 1

    print("Add this to your .env:\n")
    print(f"REFRESH_TOKEN={refresh_token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
