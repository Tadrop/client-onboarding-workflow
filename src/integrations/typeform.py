"""Typeform questionnaire client (mock + real).

The mock supports test-time injection of responses via `set_response()` so
degrade tests can simulate "client never filled the questionnaire".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..config import get_settings


@dataclass
class QuestionnaireLink:
    url: str
    form_id: str


@dataclass
class QuestionnaireResponse:
    form_id: str
    submitted: bool
    answers: dict[str, str] = field(default_factory=dict)


class TypeformClient(Protocol):
    def questionnaire_link(self, client_name: str, client_email: str) -> QuestionnaireLink: ...
    def fetch_response(self, form_id: str, client_email: str) -> QuestionnaireResponse: ...


class MockTypeformClient:
    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], QuestionnaireResponse] = {}
        self._counter = 0

    def questionnaire_link(self, client_name: str, client_email: str) -> QuestionnaireLink:
        self._counter += 1
        form_id = f"TF{self._counter:05d}"
        return QuestionnaireLink(
            url=f"https://halo-studio.typeform.com/to/{form_id}?email={client_email}",
            form_id=form_id,
        )

    def set_response(self, form_id: str, client_email: str, answers: dict[str, str]) -> None:
        self._responses[(form_id, client_email)] = QuestionnaireResponse(
            form_id=form_id, submitted=True, answers=answers
        )

    def fetch_response(self, form_id: str, client_email: str) -> QuestionnaireResponse:
        key = (form_id, client_email)
        if key not in self._responses:
            return QuestionnaireResponse(form_id=form_id, submitted=False)
        return self._responses[key]


class RealTypeformClient:  # pragma: no cover
    def __init__(self, token: str) -> None:
        self._token = token

    def questionnaire_link(self, client_name: str, client_email: str) -> QuestionnaireLink:
        raise NotImplementedError("RealTypeformClient.questionnaire_link")

    def fetch_response(self, form_id: str, client_email: str) -> QuestionnaireResponse:
        raise NotImplementedError(
            "RealTypeformClient.fetch_response: wire to GET /forms/{form_id}/responses"
        )


def make_typeform_client() -> TypeformClient:
    settings = get_settings()
    if settings.mock_integrations or not settings.typeform_api_token:
        return MockTypeformClient()
    return RealTypeformClient(settings.typeform_api_token)


__all__ = [
    "TypeformClient",
    "QuestionnaireLink",
    "QuestionnaireResponse",
    "MockTypeformClient",
    "RealTypeformClient",
    "make_typeform_client",
]
