from __future__ import annotations

from uuid import uuid4

from secure_keepass_diff.comparison import compare_databases
from secure_keepass_diff.models import Status

from .conftest import add_entry


def test_identical_changed_only_and_duplicate_titles(database_pair):
    _ap, _bp, a, b = database_pair
    same, changed, only_a, only_b = uuid4(), uuid4(), uuid4(), uuid4()
    for db in (a, b):
        add_entry(db, "Same title", entry_uuid=same)
    add_entry(a, "Duplicate", entry_uuid=changed, password="old")
    add_entry(b, "Duplicate", entry_uuid=changed, password="new")
    add_entry(a, "Duplicate", entry_uuid=only_a)
    add_entry(b, "Duplicate", entry_uuid=only_b)
    result = compare_databases(a, b)
    statuses = {entry.uuid: entry.status for entry in result.entries}
    assert statuses == {
        same: Status.IDENTICAL,
        changed: Status.CHANGED,
        only_a: Status.ONLY_A,
        only_b: Status.ONLY_B,
    }
    password_diff = next(
        d
        for e in result.entries
        if e.uuid == changed
        for d in e.differences
        if d.name == "password"
    )
    assert password_diff.secret and password_diff.a_display == password_diff.b_display == "••••••"


def test_fields_groups_tags_custom_expiry_and_attachments(database_pair):
    _ap, _bp, a, b = database_pair
    uid = uuid4()
    left = add_entry(a, "Blank", entry_uuid=uid, group="One", username="")
    right = add_entry(b, "Blank", entry_uuid=uid, group="Two", username="value")
    left.tags = ["a"]
    right.tags = ["b"]
    left.set_custom_property("x", "1")
    right.set_custom_property("x", "2")
    binary_id = b.add_binary(b"fake attachment bytes", protected=True)
    right.add_attachment(binary_id, "fake.bin")
    result = compare_databases(a, b)
    names = {d.name for d in result.entries[0].differences}
    assert {"username", "tags", "custom", "attachments", "group_path"} <= names
