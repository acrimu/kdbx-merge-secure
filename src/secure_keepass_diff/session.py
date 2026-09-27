"""Credential and loaded-database session state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DatabaseCredential:
    password: str
    keyfile: Path | None = None

    def clear(self) -> None:
        self.password = ""
        self.keyfile = None


@dataclass(slots=True)
class SecureSession:
    path_a: Path
    path_b: Path
    credential_a: DatabaseCredential
    credential_b: DatabaseCredential
    hash_a: bytes
    hash_b: bytes
    db_a: Any
    db_b: Any

    def clear(self) -> None:
        self.credential_a.clear()
        self.credential_b.clear()
        self.db_a = None
        self.db_b = None
