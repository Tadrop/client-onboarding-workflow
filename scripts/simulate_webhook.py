"""Locally simulate an e-sign webhook hitting the running server.

Usage (with the app running at http://127.0.0.1:8000):

    python scripts/simulate_webhook.py docusign new
    python scripts/simulate_webhook.py docusign renewal
    python scripts/simulate_webhook.py pandadoc new
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=["docusign", "pandadoc"])
    parser.add_argument("variant", choices=["new", "renewal"])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    fixture = FIXTURES / f"{args.provider}_{args.variant}.json"
    if not fixture.exists():
        print(f"missing fixture: {fixture}", file=sys.stderr)
        return 2
    body = fixture.read_bytes()

    if args.provider == "docusign":
        secret = os.environ.get("DOCUSIGN_WEBHOOK_SECRET", "replace-me")
        header = {"X-DocuSign-Signature-1": sign(body, secret)}
        endpoint = f"{args.url}/webhooks/docusign"
    else:
        secret = os.environ.get("PANDADOC_WEBHOOK_SECRET", "replace-me")
        header = {"X-Pandadoc-Signature": sign(body, secret)}
        endpoint = f"{args.url}/webhooks/pandadoc"

    resp = httpx.post(endpoint, content=body, headers=header, timeout=15.0)
    print(f"{resp.status_code} {endpoint}")
    print(json.dumps(resp.json(), indent=2))
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
