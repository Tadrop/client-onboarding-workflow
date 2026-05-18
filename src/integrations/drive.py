"""Google Drive folder creator (mock + real).

Combines the standard `drive_template.yaml` subfolders with phase folders
defined by the per-service template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import yaml

from ..config import CONFIG_DIR, get_settings


@dataclass
class DriveFolder:
    id: str
    name: str
    parent_id: str | None = None
    subfolders: list[DriveFolder] = field(default_factory=list)


class DriveClient(Protocol):
    def folder_structure(self, client_name: str, service_type: str) -> list[str]: ...
    def create_client_folder(self, client_name: str, service_type: str) -> DriveFolder: ...
    def refresh(self, folder_id: str) -> None: ...


def _load_drive_template() -> dict:
    with (CONFIG_DIR / "drive_template.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_service_template(service_type: str) -> dict | None:
    path = CONFIG_DIR / "service_templates" / f"{service_type}.yaml"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_subfolders(service_type: str) -> list[str]:
    """Standard subfolders + phase subfolders from service template (deduped)."""
    drive_template = _load_drive_template()
    standard = list(drive_template.get("standard_subfolders", []))
    service = _load_service_template(service_type)
    phase_folders = service.get("drive", {}).get("folders", []) if service else []
    seen: set[str] = set()
    combined: list[str] = []
    for name in standard + phase_folders:
        if name not in seen:
            combined.append(name)
            seen.add(name)
    return combined


class MockDriveClient:
    def __init__(self) -> None:
        self._folders: dict[str, DriveFolder] = {}
        self._counter = 0

    def folder_structure(self, client_name: str, service_type: str) -> list[str]:
        return _build_subfolders(service_type)

    def create_client_folder(self, client_name: str, service_type: str) -> DriveFolder:
        drive_template = _load_drive_template()
        root_name = drive_template["root_pattern"].format(
            client_name=client_name, service_type=service_type.title()
        )
        self._counter += 1
        root = DriveFolder(id=f"DR{self._counter:05d}", name=root_name)
        for sub_name in self.folder_structure(client_name, service_type):
            self._counter += 1
            root.subfolders.append(
                DriveFolder(id=f"DR{self._counter:05d}", name=sub_name, parent_id=root.id)
            )
        self._folders[root.id] = root
        return root

    def refresh(self, folder_id: str) -> None:
        if folder_id not in self._folders:
            raise LookupError(f"unknown drive folder: {folder_id}")

    @property
    def folders(self) -> dict[str, DriveFolder]:
        return dict(self._folders)


class RealDriveClient:  # pragma: no cover
    def __init__(self, credentials_path: str, parent_folder_id: str) -> None:
        self._credentials_path = credentials_path
        self._parent_folder_id = parent_folder_id

    def folder_structure(self, client_name: str, service_type: str) -> list[str]:
        return _build_subfolders(service_type)

    def create_client_folder(self, client_name: str, service_type: str) -> DriveFolder:
        raise NotImplementedError(
            "RealDriveClient.create_client_folder: wire to Drive API "
            "files.create with mimeType=application/vnd.google-apps.folder"
        )

    def refresh(self, folder_id: str) -> None:
        raise NotImplementedError("RealDriveClient.refresh")


def make_drive_client() -> DriveClient:
    settings = get_settings()
    if settings.mock_integrations or not settings.google_drive_credentials_path:
        return MockDriveClient()
    return RealDriveClient(
        settings.google_drive_credentials_path, settings.google_drive_parent_folder_id
    )


__all__ = [
    "DriveClient",
    "DriveFolder",
    "MockDriveClient",
    "RealDriveClient",
    "make_drive_client",
]
