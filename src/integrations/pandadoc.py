"""PandaDoc webhook payload parser + signature verifier.

Same HMAC-SHA256 / hex scheme as the DocuSign module — see that module's
docstring for the rationale on portability.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from ..config import get_settings
from ..schemas import (
    ClientContact,
    Contract,
    ContractType,
    EsignProvider,
    ServiceType,
)
from .base import WebhookSignatureError


def verify_signature(body: bytes, signature_header: str | None) -> None:
    secret = get_settings().pandadoc_webhook_secret.encode("utf-8")
    if not signature_header:
        raise WebhookSignatureError("missing pandadoc signature header")
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header.strip()):
        raise WebhookSignatureError("pandadoc signature mismatch")


def parse_event(payload: dict[str, Any]) -> Contract:
    """Map a PandaDoc `document_state_changed` (completed) payload."""
    data = payload.get("data", payload)
    doc_id = data["id"]
    metadata = data.get("metadata", {}) or {}
    contract_type_raw = (metadata.get("contract_type") or "new").lower()
    service_type_raw = (metadata.get("service_type") or "branding").lower()
    recipients = data.get("recipients", []) or []
    contacts = [
        ClientContact(
            name=r.get("first_name", "") + " " + r.get("last_name", ""),
            email=r["email"],
            role=r.get("role"),
        )
        for r in recipients
        if r.get("email")
    ]
    return Contract(
        provider=EsignProvider.PANDADOC,
        envelope_id=doc_id,
        contract_type=ContractType(contract_type_raw),
        service_type=ServiceType(service_type_raw),
        client_name=metadata.get("client_name") or data.get("name", "New Client"),
        client_contacts=contacts,
        existing_client_id=metadata.get("existing_client_id"),
        envelope_subject=data.get("name"),
        raw_metadata={**metadata, "_raw_provider": "pandadoc"},
    )
