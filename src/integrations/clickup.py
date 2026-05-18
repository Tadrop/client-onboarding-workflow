"""ClickUp project + task creator.

Templates are loaded from `config/service_templates/<service>.yaml`. If the
service-type has no template, we raise — failing loud is intentional
(`CLAUDE.md` §6 step 4c: ClickUp template missing → fail loud).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from ..config import CONFIG_DIR, get_settings
from .base import TemplateMissingError


@dataclass
class ClickUpTask:
    id: str
    name: str


@dataclass
class ClickUpPhase:
    name: str
    tasks: list[ClickUpTask] = field(default_factory=list)


@dataclass
class ClickUpProject:
    id: str
    name: str
    template_name: str
    phases: list[ClickUpPhase] = field(default_factory=list)


class ClickUpClient(Protocol):
    def load_template(self, service_type: str) -> dict: ...
    def create_project(self, client_name: str, service_type: str) -> ClickUpProject: ...
    def update_project_dates(self, project_id: str, **dates: str) -> None: ...


def _load_template(service_type: str) -> dict:
    path = CONFIG_DIR / "service_templates" / f"{service_type}.yaml"
    if not path.exists():
        raise TemplateMissingError(
            f"no ClickUp template configured for service_type={service_type!r} (expected {path})"
        )
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class MockClickUpClient:
    def __init__(self) -> None:
        self._projects: dict[str, ClickUpProject] = {}
        self._counter = 0

    def load_template(self, service_type: str) -> dict:
        return _load_template(service_type)

    def create_project(self, client_name: str, service_type: str) -> ClickUpProject:
        template = self.load_template(service_type)
        ck = template["clickup"]
        self._counter += 1
        project_id = f"CU{self._counter:05d}"
        phases: list[ClickUpPhase] = []
        task_counter = 0
        for phase in ck.get("phases", []):
            tasks: list[ClickUpTask] = []
            for tname in phase.get("tasks", []):
                task_counter += 1
                tasks.append(ClickUpTask(id=f"T{task_counter:05d}", name=tname))
            phases.append(ClickUpPhase(name=phase["name"], tasks=tasks))
        project = ClickUpProject(
            id=project_id,
            name=f"{client_name} — {service_type.title()}",
            template_name=ck.get("template_name", service_type),
            phases=phases,
        )
        self._projects[project_id] = project
        return project

    def update_project_dates(self, project_id: str, **dates: str) -> None:
        if project_id not in self._projects:
            raise LookupError(f"unknown clickup project: {project_id}")

    @property
    def projects(self) -> dict[str, ClickUpProject]:
        return dict(self._projects)


class RealClickUpClient:  # pragma: no cover - placeholder
    def __init__(self, token: str, workspace_id: str) -> None:
        self._token = token
        self._workspace_id = workspace_id

    def load_template(self, service_type: str) -> dict:
        return _load_template(service_type)

    def create_project(self, client_name: str, service_type: str) -> ClickUpProject:
        raise NotImplementedError(
            "RealClickUpClient.create_project: wire to ClickUp API "
            "POST /api/v2/team/{workspace}/space + folder + list"
        )

    def update_project_dates(self, project_id: str, **dates: str) -> None:
        raise NotImplementedError("RealClickUpClient.update_project_dates")


def make_clickup_client() -> ClickUpClient:
    settings = get_settings()
    if settings.mock_integrations or not settings.clickup_api_token:
        return MockClickUpClient()
    return RealClickUpClient(settings.clickup_api_token, settings.clickup_workspace_id)


__all__ = [
    "ClickUpClient",
    "ClickUpProject",
    "ClickUpPhase",
    "ClickUpTask",
    "MockClickUpClient",
    "RealClickUpClient",
    "make_clickup_client",
]
_ = Path
