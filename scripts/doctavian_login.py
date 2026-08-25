"""Obtain a Doctavian bearer token through their Microsoft OAuth proxy.

Their gateway wants two credentials: the x-api-key that names the environment,
and a Microsoft token that names the caller. The key alone answers
"Authorization header is missing", which is the point this script exists to fix.

Authorization code with PKCE, exactly as their Postman collection declares it.
Run it, open the printed URL, sign in, then paste the code from the callback.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sys
import urllib.parse

import httpx

BASE = "https://demo.api.doctavian.com"
PROVIDER = "microsoft"
CLIENT_ID = "11e71170-3499-43f3-b878-7df343f43d37"
SCOPE = "api://40728276-52a7-4932-bf32-76737f1fd01a/.default offline_access"
REDIRECT = "https://oauth.pstmn.io/v1/callback"


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


def main() -> int:
    verifier, challenge = _pkce()
    query = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT,
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": secrets.token_urlsafe(16),
        }
    )
    print("\n  Open this and sign in with the Doctavian account:\n")
    print(f"  {BASE}/public/v1/auth/{PROVIDER}/authorize?{query}\n")
    print("  You land on a Postman callback page showing an authorization code.")
    code = input("  Paste the code here: ").strip()
    if not code:
        print("  No code given.")
        return 1

    response = httpx.post(
        f"{BASE}/public/v1/auth/{PROVIDER}/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "scope": SCOPE,
        },
        headers={"x-api-key": os.environ.get("DOCTAVIAN_API_KEY", "")},
        timeout=30,
    )
    if not response.is_success:
        print(f"\n  Token exchange failed: {response.status_code}\n  {response.text[:400]}")
        return 1

    token = response.json().get("access_token", "")
    if not token:
        print(f"\n  No access_token in the response:\n  {response.text[:400]}")
        return 1

    print(f"\n  Token acquired, {len(token)} characters. Put this in .env:\n")
    print(f"DOCTAVIAN_TOKEN={token}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
