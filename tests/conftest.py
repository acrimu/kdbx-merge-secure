from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pykeepass import PyKeePass, create_database

PASSWORD_A = "synthetic-A-master-only"
PASSWORD_B = "synthetic-B-master-only"


def make_db(path: Path, password: str) -> PyKeePass:
    create_database(str(path), password=password)
    return PyKeePass(str(path), password=password)


def add_entry(
    db: PyKeePass,
    title: str,
    *,
    entry_uuid: UUID | None = None,
    group: str = "General",
    password: str = "fake-entry-secret",
    username: str = "fake-user",
):
    target = db.find_groups(name=group, first=True) or db.add_group(db.root_group, group)
    entry = db.add_entry(target, title, username, password, force_creation=True)
    if entry_uuid is not None:
        entry.uuid = entry_uuid
    return entry


@pytest.fixture
def database_pair(tmp_path: Path):
    a_path, b_path = tmp_path / "a.kdbx", tmp_path / "b.kdbx"
    a, b = make_db(a_path, PASSWORD_A), make_db(b_path, PASSWORD_B)
    return a_path, b_path, a, b
