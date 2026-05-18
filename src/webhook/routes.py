"""Webhook HTTP routes for DocuSign and PandaDoc."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from ..integrations import docusign, pandadoc
from ..integrations.base import WebhookSignatureError
from ..logging_setup import get_logger
from ..milestones.orchestrator import start_run

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger(__name__)


@router.post("/docusign", status_code=status.HTTP_202_ACCEPTED)
async def docusign_webhook(
    request: Request,
    x_docusign_signature_1: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    try:
        docusign.verify_signature(body, x_docusign_signature_1)
    except WebhookSignatureError as e:
        log.warning("webhook.docusign.invalid_signature", error=str(e))
        raise HTTPException(status_code=401, detail="invalid signature") from e

    payload = json.loads(body)
    event = payload.get("event") or payload.get("status")
    if event and event.lower() not in ("envelope-completed", "completed", "envelope_completed"):
        return {"status": "ignored", "event": event}

    contract = docusign.parse_event(payload)
    run = start_run(contract)
    log.info(
        "webhook.docusign.accepted",
        envelope_id=contract.envelope_id,
        run_id=run.run_id,
        contract_type=run.contract.contract_type.value,
    )
    return {"status": "accepted", "run_id": run.run_id}


@router.post("/pandadoc", status_code=status.HTTP_202_ACCEPTED)
async def pandadoc_webhook(
    request: Request,
    x_pandadoc_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    try:
        pandadoc.verify_signature(body, x_pandadoc_signature)
    except WebhookSignatureError as e:
        log.warning("webhook.pandadoc.invalid_signature", error=str(e))
        raise HTTPException(status_code=401, detail="invalid signature") from e

    payload = json.loads(body)
    data = payload.get("data") or payload
    state = data.get("status")
    if state and state.lower() not in ("document.completed", "completed"):
        return {"status": "ignored", "state": state}

    contract = pandadoc.parse_event(payload)
    run = start_run(contract)
    log.info(
        "webhook.pandadoc.accepted",
        envelope_id=contract.envelope_id,
        run_id=run.run_id,
        contract_type=run.contract.contract_type.value,
    )
    return {"status": "accepted", "run_id": run.run_id}
