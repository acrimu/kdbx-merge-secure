"""Pure snapshot comparison, independent from the GUI."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from .models import ComparedEntry, ComparisonResult, EntrySnapshot, FieldDiff, Status


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _display(name: str, value: object) -> str:
    """Create a readable comparison value without exposing password fields."""
    if name == "password":
        return "••••••"
    if value is None:
        return "—"
    if name == "attachments":
        attachments = value if isinstance(value, tuple) else ()
        return ", ".join(f"{filename} ({len(data)} bytes)" for filename, data in attachments) or "—"
    if name == "custom" and hasattr(value, "items"):
        return "\n".join(f"{key} = {item}" for key, item in sorted(value.items())) or "—"
    if name == "tags":
        return ", ".join(value) if isinstance(value, tuple) else _text(value)
    if name == "group_path":
        return "/".join(value) if isinstance(value, tuple) else _text(value)
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return _text(value) or "—"


def _group_path(entry: Any) -> tuple[str, ...]:
    names: list[str] = []
    group = entry.group
    while group is not None and group.parentgroup is not None:
        names.append(_text(group.name))
        group = group.parentgroup
    return tuple(reversed(names))


def snapshot(entry: Any) -> EntrySnapshot:
    attachments = tuple(sorted((a.filename, bytes(a.data)) for a in entry.attachments))
    custom = MappingProxyType(dict(entry.custom_properties or {}))
    unsupported: list[str] = []
    if getattr(entry, "autotype_enabled", None) not in (None, True):
        unsupported.append("non-default auto-type settings")
    return EntrySnapshot(
        uuid=entry.uuid,
        title=_text(entry.title),
        group_path=_group_path(entry),
        username=_text(entry.username),
        password=_text(entry.password),
        url=_text(entry.url),
        notes=_text(entry.notes),
        tags=tuple(sorted(entry.tags or [])),
        custom=custom,
        expires=bool(entry.expires),
        expiry_time=entry.expiry_time,
        ctime=entry.ctime,
        mtime=entry.mtime,
        atime=entry.atime,
        icon=getattr(entry, "icon", None),
        attachments=attachments,
        history_count=len(getattr(entry, "history", []) or []),
        unsupported=tuple(unsupported),
    )


def snapshots(database: Any) -> dict[object, EntrySnapshot]:
    return {entry.uuid: snapshot(entry) for entry in database.entries}


def compare_databases(db_a: Any, db_b: Any) -> ComparisonResult:
    a, b = snapshots(db_a), snapshots(db_b)
    results: list[ComparedEntry] = []
    names = (
        "title",
        "username",
        "password",
        "url",
        "notes",
        "tags",
        "custom",
        "expires",
        "expiry_time",
        "ctime",
        "mtime",
        "atime",
        "icon",
        "attachments",
        "history_count",
        "group_path",
    )
    for entry_uuid in sorted(set(a) | set(b), key=str):
        left, right = a.get(entry_uuid), b.get(entry_uuid)
        if left is None:
            assert right is not None
            results.append(
                ComparedEntry(right.uuid, right.title, None, right.group_path, Status.ONLY_B)
            )
            continue
        if right is None:
            results.append(
                ComparedEntry(left.uuid, left.title, left.group_path, None, Status.ONLY_A)
            )
            continue
        diffs: list[FieldDiff] = []
        for name in names:
            av, bv = getattr(left, name), getattr(right, name)
            if av != bv:
                secret = name == "password"
                diffs.append(
                    FieldDiff(
                        name,
                        _display(name, av),
                        _display(name, bv),
                        secret,
                    )
                )
        warnings = tuple(sorted(set(left.unsupported + right.unsupported)))
        status = Status.UNSUPPORTED if warnings else (Status.CHANGED if diffs else Status.IDENTICAL)
        newer = "unknown"
        if left.mtime and right.mtime and left.mtime != right.mtime:
            newer = "A" if left.mtime > right.mtime else "B"
        results.append(
            ComparedEntry(
                left.uuid,
                left.title or right.title,
                left.group_path,
                right.group_path,
                status,
                tuple(diffs),
                newer,
                warnings,
            )
        )
    return ComparisonResult(tuple(results))
