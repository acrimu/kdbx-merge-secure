"""Read-only loading and input integrity helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pykeepass import PyKeePass

from .errors import sanitize_error
from .session import DatabaseCredential, SecureSession


def resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=True)


def file_digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def open_database(path: Path, credential: DatabaseCredential) -> Any:
    try:
        return PyKeePass(
            str(path),
            password=credential.password,
            keyfile=str(credential.keyfile) if credential.keyfile else None,
        )
    except Exception as exc:
        raise sanitize_error(exc, "Database could not be unlocked") from None


def load_session(
    path_a: Path,
    credential_a: DatabaseCredential,
    path_b: Path,
    credential_b: DatabaseCredential,
) -> SecureSession:
    a, b = resolved(path_a), resolved(path_b)
    hash_a, hash_b = file_digest(a), file_digest(b)
    try:
        db_a = open_database(a, credential_a)
        db_b = open_database(b, credential_b)
    except Exception:
        credential_a.clear()
        credential_b.clear()
        raise
    return SecureSession(a, b, credential_a, credential_b, hash_a, hash_b, db_a, db_b)


def verify_inputs(session: SecureSession) -> None:
    if (
        file_digest(session.path_a) != session.hash_a
        or file_digest(session.path_b) != session.hash_b
    ):
        raise ValueError("An input database changed during this session; saving was aborted.")
