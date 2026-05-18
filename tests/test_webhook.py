"""HTTP webhook + review queue smoke tests."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client():
    from src.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _docusign_secret() -> str:
    from src.config import get_settings

    return get_settings().docusign_webhook_secret


def _pandadoc_secret() -> str:
    from src.config import get_settings

    return get_settings().pandadoc_webhook_secret


def test_docusign_new_webhook_starts_run(client) -> None:
    body = (FIXTURES / "docusign_new.json").read_bytes()
    sig = _sign(body, _docusign_secret())
    resp = client.post(
        "/webhooks/docusign",
        content=body,
        headers={"X-DocuSign-Signature-1": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 202
    body_json = resp.json()
    assert body_json["status"] == "accepted"
    run_id = body_json["run_id"]

    detail = client.get(f"/runs/{run_id}").json()
    assert detail["run"]["contract"]["contract_type"] == "new"
    assert any(d["kind"] == "welcome_email" for d in detail["drafts"])


def test_docusign_invalid_signature_rejected(client) -> None:
    body = (FIXTURES / "docusign_new.json").read_bytes()
    resp = client.post(
        "/webhooks/docusign",
        content=body,
        headers={"X-DocuSign-Signature-1": "not-the-right-sig"},
    )
    assert resp.status_code == 401


def test_pandadoc_new_webhook_starts_run(client) -> None:
    body = (FIXTURES / "pandadoc_new.json").read_bytes()
    sig = _sign(body, _pandadoc_secret())
    resp = client.post(
        "/webhooks/pandadoc",
        content=body,
        headers={"X-Pandadoc-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_pandadoc_renewal_skips_welcome(client) -> None:
    body = (FIXTURES / "pandadoc_renewal.json").read_bytes()
    sig = _sign(body, _pandadoc_secret())
    resp = client.post(
        "/webhooks/pandadoc",
        content=body,
        headers={"X-Pandadoc-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    detail = client.get(f"/runs/{run_id}").json()
    assert detail["run"]["contract"]["contract_type"] == "renewal"
    assert "welcome" not in detail["run"]["milestones"]
    assert detail["drafts"] == []


def test_approval_endpoint_advances_pipeline(client) -> None:
    body = (FIXTURES / "docusign_new.json").read_bytes()
    sig = _sign(body, _docusign_secret())
    resp = client.post(
        "/webhooks/docusign",
        content=body,
        headers={"X-DocuSign-Signature-1": sig},
    )
    run_id = resp.json()["run_id"]
    pending = client.get("/reviews").json()
    assert pending
    review_id = pending[0]["review_id"]
    approved = client.post(
        f"/reviews/{review_id}/approve",
        json={"reviewer_email": "priya@halo.studio"},
    )
    assert approved.status_code == 200
    assert approved.json()["review"]["decision"] == "approved"

    detail = client.get(f"/runs/{run_id}").json()
    welcome = detail["run"]["milestones"]["welcome"]
    internal = detail["run"]["milestones"]["internal_setup"]
    assert welcome["state"] == "done"
    assert internal["state"] == "done"
