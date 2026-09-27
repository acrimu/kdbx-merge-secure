from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pykeepass import PyKeePass, create_database

from secure_keepass_diff.comparison import compare_databases
from secure_keepass_diff.errors import SafeError
from secure_keepass_diff.loading import load_session
from secure_keepass_diff.merge import execute_merge, validate_destination
from secure_keepass_diff.models import MergePlan, PlanItem, Resolution
from secure_keepass_diff.planning import automatic_plan
from secure_keepass_diff.session import DatabaseCredential

from .conftest import PASSWORD_A, PASSWORD_B, add_entry


def loaded(database_pair):
    ap, bp, a, b = database_pair
    a.save()
    b.save()
    session = load_session(ap, DatabaseCredential(PASSWORD_A), bp, DatabaseCredential(PASSWORD_B))
    return session, compare_databases(session.db_a, session.db_b)


def test_keep_use_import_ignore_exclude_and_originals_unchanged(database_pair, tmp_path: Path):
    ap, bp, a, b = database_pair
    changed, only_a, only_b = uuid4(), uuid4(), uuid4()
    add_entry(a, "Changed", entry_uuid=changed, password="a")
    add_entry(b, "Changed", entry_uuid=changed, password="b")
    add_entry(a, "Remove", entry_uuid=only_a)
    add_entry(b, "Import", entry_uuid=only_b)
    session, comparison = loaded(database_pair)
    before_a, before_b = ap.read_bytes(), bp.read_bytes()
    plan = (
        MergePlan()
        .resolve(PlanItem(changed, Resolution.USE_B))
        .resolve(PlanItem(only_a, Resolution.EXCLUDE))
        .resolve(PlanItem(only_b, Resolution.USE_B))
    )
    output = execute_merge(session, comparison, plan, tmp_path / "merged.kdbx")
    merged = PyKeePass(str(output), password=PASSWORD_A)
    assert merged.find_entries(uuid=changed, first=True).password == "b"
    assert merged.find_entries(uuid=only_a, first=True) is None
    assert merged.find_entries(uuid=only_b, first=True).title == "Import"
    assert ap.read_bytes() == before_a and bp.read_bytes() == before_b


def test_keep_both_and_field_merge(database_pair, tmp_path: Path):
    _ap, _bp, a, b = database_pair
    both, fields = uuid4(), uuid4()
    add_entry(a, "Left", entry_uuid=both)
    add_entry(b, "Right", entry_uuid=both)
    add_entry(a, "Title A", entry_uuid=fields, username="user-a")
    add_entry(b, "Title B", entry_uuid=fields, username="user-b")
    session, comparison = loaded(database_pair)
    plan = (
        MergePlan()
        .resolve(PlanItem(both, Resolution.KEEP_BOTH))
        .resolve(PlanItem(fields, Resolution.FIELD_MERGE, {"title": "B", "username": "A"}))
    )
    merged_path = execute_merge(session, comparison, plan, tmp_path / "out.kdbx")
    merged = PyKeePass(str(merged_path), password=PASSWORD_A)
    assert len([e for e in merged.entries if e.title.startswith(("Left", "Right"))]) == 2
    entry = merged.find_entries(uuid=fields, first=True)
    assert entry.title == "Title B" and entry.username == "user-a"


def test_unresolved_and_input_output_protections(database_pair, tmp_path: Path):
    ap, _bp, a, b = database_pair
    add_entry(a, "A", entry_uuid=uuid4())
    session, comparison = loaded(database_pair)
    with pytest.raises(SafeError):
        execute_merge(session, comparison, MergePlan(), tmp_path / "out.kdbx")
    with pytest.raises(SafeError):
        validate_destination(session, ap)
    ap.write_bytes(ap.read_bytes() + b"changed")
    plan = MergePlan().resolve(PlanItem(comparison.entries[0].uuid, Resolution.KEEP_A))
    with pytest.raises(ValueError):
        execute_merge(session, comparison, plan, tmp_path / "changed.kdbx")


def test_wrong_password_and_corruption(database_pair, tmp_path: Path):
    ap, bp, a, b = database_pair
    a.save()
    b.save()
    from secure_keepass_diff.loading import open_database

    with pytest.raises(SafeError):
        open_database(ap, DatabaseCredential("wrong"))
    broken = tmp_path / "broken.kdbx"
    broken.write_bytes(b"not a database")
    with pytest.raises(SafeError):
        open_database(broken, DatabaseCredential("wrong"))


def test_separate_optional_key_files(tmp_path: Path):
    key_a, key_b = tmp_path / "a.key", tmp_path / "b.key"
    key_a.write_bytes(b"A" * 32)
    key_b.write_bytes(b"B" * 32)
    path_a, path_b = tmp_path / "key-a.kdbx", tmp_path / "key-b.kdbx"
    create_database(str(path_a), password=PASSWORD_A, keyfile=str(key_a))
    create_database(str(path_b), password=PASSWORD_B, keyfile=str(key_b))
    session = load_session(
        path_a,
        DatabaseCredential(PASSWORD_A, key_a),
        path_b,
        DatabaseCredential(PASSWORD_B, key_b),
    )
    assert session.db_a is not None and session.db_b is not None


def test_failure_cleans_encrypted_temporary_output(database_pair, tmp_path: Path, monkeypatch):
    _ap, _bp, a, _b = database_pair
    only_a = uuid4()
    add_entry(a, "Keep", entry_uuid=only_a)
    session, comparison = loaded(database_pair)
    plan = MergePlan().resolve(PlanItem(only_a, Resolution.KEEP_A))

    def fail(*_args, **_kwargs):
        raise OSError("synthetic interruption")

    monkeypatch.setattr("secure_keepass_diff.merge._apply_plan", fail)
    with pytest.raises(SafeError):
        execute_merge(session, comparison, plan, tmp_path / "failed.kdbx")
    assert not list(tmp_path.glob(".secure-keepass-diff-*.kdbx"))
    assert not (tmp_path / "failed.kdbx").exists()


def test_existing_output_is_never_overwritten(database_pair, tmp_path: Path):
    session, _comparison = loaded(database_pair)
    output = tmp_path / "existing.kdbx"
    output.write_bytes(b"sentinel")
    with pytest.raises(SafeError):
        validate_destination(session, output)
    assert output.read_bytes() == b"sentinel"


def test_gui_string_resolution_is_normalized():
    entry_uuid = uuid4()
    item = PlanItem(entry_uuid, "keep_a")  # type: ignore[arg-type]
    assert item.resolution is Resolution.KEEP_A
    assert item.resolution.value == "keep_a"


def test_expiration_only_difference_can_merge_later_b(database_pair, tmp_path: Path):
    _ap, _bp, a, b = database_pair
    entry_uuid = uuid4()
    earlier = datetime.now(UTC) + timedelta(days=1)
    later = earlier + timedelta(days=30)
    left = add_entry(a, "Expiry", entry_uuid=entry_uuid)
    right = add_entry(b, "Expiry", entry_uuid=entry_uuid)
    right.ctime = left.ctime
    left.expires = True
    right.expires = True
    left.expiry_time = earlier
    right.expiry_time = later
    session, comparison = loaded(database_pair)
    plan = automatic_plan(session, comparison)
    assert plan.items[entry_uuid].resolution is Resolution.FIELD_MERGE
    output = execute_merge(session, comparison, plan, tmp_path / "later-expiry.kdbx")
    merged = PyKeePass(str(output), password=PASSWORD_A)
    result = merged.find_entries(uuid=entry_uuid, first=True)
    assert result.expiry_time == later.replace(microsecond=0)


def test_one_sided_entries_are_resolved_automatically(database_pair):
    _ap, _bp, a, b = database_pair
    only_a, only_b = uuid4(), uuid4()
    add_entry(a, "Only A", entry_uuid=only_a)
    add_entry(b, "Only B", entry_uuid=only_b)
    session, comparison = loaded(database_pair)
    plan = automatic_plan(session, comparison)
    assert plan.items[only_a].resolution is Resolution.KEEP_A
    assert plan.items[only_b].resolution is Resolution.USE_B
    assert not plan.unresolved(comparison)


def test_import_allows_duplicate_title_and_username(database_pair, tmp_path: Path):
    _ap, _bp, a, b = database_pair
    existing_uuid, imported_uuid = uuid4(), uuid4()
    add_entry(a, "Duplicate", entry_uuid=existing_uuid, username="same-user")
    add_entry(b, "Duplicate", entry_uuid=imported_uuid, username="same-user")
    session, comparison = loaded(database_pair)
    plan = automatic_plan(session, comparison)
    output = execute_merge(session, comparison, plan, tmp_path / "duplicates.kdbx")
    merged = PyKeePass(str(output), password=PASSWORD_A)
    matches = [
        entry
        for entry in merged.entries
        if entry.title == "Duplicate" and entry.username == "same-user"
    ]
    assert {entry.uuid for entry in matches} == {existing_uuid, imported_uuid}
