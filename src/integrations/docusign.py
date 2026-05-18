"""DocuSign webhook payload parser + signature verifier.

The signature scheme used here is a generic HMAC-SHA256 over the raw body,
hex-encoded — production setups should match whatever Connect / HMAC scheme
DocuSign provides. The point for this codebase is: the parser is testable
without hitting DocuSign, and the verifier raises on tampered bodies.
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
    secret = get_settings().docusign_webhook_secret.encode("utf-8")
    if not signature_header:
        raise WebhookSignatureError("missing docusign signature header")
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header.strip()):
        raise WebhookSignatureError("docusign signature mismatch")


def parse_event(payload: dict[str, Any]) -> Contract:
    """Map a DocuSign `envelope_completed` payload to our `Contract` schema."""
    envelope_id: str = payload["envelopeId"]
    custom = _flatten_custom_fields(payload.get("customFields", {}))
    contract_type = ContractType(custom.get("contract_type", "new").lower())
    service_type = ServiceType(custom.get("service_type", "branding").lower())
    recipients = payload.get("recipients", {}).get("signers", []) or []
    contacts = [
        ClientContact(name=r["name"], email=r["email"], role=r.get("roleName"))
        for r in recipients
        if r.get("email")
    ]
    return Contract(
        provider=EsignProvider.DOCUSIGN,
        envelope_id=envelope_id,
        contract_type=contract_type,
        service_type=service_type,
        client_name=custom.get("client_name") or payload.get("emailSubject", "New Client"),
        client_contacts=contacts,
        existing_client_id=custom.get("existing_client_id"),
        envelope_subject=payload.get("emailSubject"),
        raw_metadata={**custom, "_raw_provider": "docusign"},
    )


def _flatten_custom_fields(cf: dict[str, Any]) -> dict[str, Any]:
    """DocuSign nests text + list custom fields; flatten to `name → value`."""
    out: dict[str, Any] = {}
    for collection in ("textCustomFields", "listCustomFields"):
        for entry in cf.get(collection, []):
            name = entry.get("name")
            if name:
                out[name] = entry.get("value")
    return out
