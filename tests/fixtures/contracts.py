"""Test contract factories — keeps the test code readable."""

from __future__ import annotations

from src.schemas import (
    ClientContact,
    Contract,
    ContractType,
    EsignProvider,
    ServiceType,
)


def new_contract(
    *,
    client_name: str = "Acme & Co.",
    service_type: ServiceType = ServiceType.BRANDING,
    envelope_id: str = "env_new_001",
    contract_type: ContractType = ContractType.NEW,
    contacts: list[ClientContact] | None = None,
    existing_client_id: str | None = None,
    envelope_subject: str | None = "Acme branding engagement — SoW",
    raw_metadata: dict | None = None,
) -> Contract:
    return Contract(
        provider=EsignProvider.DOCUSIGN,
        envelope_id=envelope_id,
        contract_type=contract_type,
        service_type=service_type,
        client_name=client_name,
        client_contacts=contacts
        or [ClientContact(name="Jane Client", email="jane@acme.example", role="ceo")],
        existing_client_id=existing_client_id,
        envelope_subject=envelope_subject,
        raw_metadata=raw_metadata or {},
    )


def renewal_contract(**overrides) -> Contract:
    defaults = dict(
        client_name="Acme & Co.",
        envelope_id="env_renewal_001",
        contract_type=ContractType.RENEWAL,
        service_type=ServiceType.RETAINER,
        existing_client_id="cli_acme_001",
        envelope_subject="Acme retainer — renewal",
        raw_metadata={"contract_type": "renewal", "existing_client_id": "cli_acme_001"},
    )
    defaults.update(overrides)
    return new_contract(**defaults)
