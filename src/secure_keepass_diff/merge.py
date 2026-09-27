"""Apply a finalized plan only to an encrypted temporary KDBX copy."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .errors import SafeError, sanitize_error
from .loading import open_database, verify_inputs
from .models import ComparisonResult, MergePlan, Resolution, Status
from .session import SecureSession

MERGEABLE_FIELDS = frozenset(
    {
        "title",
        "username",
        "password",
        "url",
        "notes",
        "tags",
        "custom",
        "expires",
        "expiry_time",
        "icon",
    }
)


def same_path(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except (FileNotFoundError, OSError):
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
            str(right.resolve(strict=False))
        )


def validate_destination(session: SecureSession, destination: Path) -> Path:
    output = destination.expanduser().resolve(strict=False)
    if output.suffix.lower() != ".kdbx":
        raise SafeError("The output filename must end in .kdbx.")
    if same_path(output, session.path_a) or same_path(output, session.path_b):
        raise SafeError("The output must be a new file and cannot be either input database.")
    if output.exists():
        raise SafeError("The selected output already exists. Choose a new filename.")
    if not output.parent.is_dir():
        raise SafeError("The selected output directory does not exist.")
    return output


def _find_entry(database: Any, entry_uuid: UUID) -> Any | None:
    return database.find_entries(uuid=entry_uuid, first=True)


def _ensure_group(database: Any, path: tuple[str, ...]) -> Any:
    group = database.root_group
    for name in path:
        child = next((candidate for candidate in group.subgroups if candidate.name == name), None)
        group = child or database.add_group(group, name)
    return group


def _copy_supported(
    target_db: Any, target: Any, source: Any, fields: set[str] | None = None
) -> None:
    selected = MERGEABLE_FIELDS if fields is None else fields
    for name in ("title", "username", "password", "url", "notes"):
        if name in selected:
            setattr(target, name, getattr(source, name) or "")
    for name in ("expires", "expiry_time", "icon"):
        if name in selected and getattr(source, name) is not None:
            setattr(target, name, getattr(source, name))
    if "tags" in selected:
        target.tags = list(source.tags or [])
    if "custom" in selected:
        for key in list(target.custom_properties):
            target.delete_custom_property(key)
        for key, value in (source.custom_properties or {}).items():
            target.set_custom_property(key, value or "")


def _clone_entry(target_db: Any, source: Any, new_uuid: bool) -> Any:
    path: list[str] = []
    group = source.group
    while group is not None and group.parentgroup is not None:
        path.append(group.name or "")
        group = group.parentgroup
    target_group = _ensure_group(target_db, tuple(reversed(path)))
    entry = target_db.add_entry(
        target_group,
        source.title or "",
        source.username or "",
        source.password or "",
        url=source.url or "",
        notes=source.notes or "",
        expiry_time=source.expiry_time,
        icon=getattr(source, "icon", None),
        force_creation=True,
    )
    if not new_uuid:
        entry.uuid = source.uuid
    else:
        entry.uuid = uuid4()
        entry.title = f"{entry.title} (from B)"
    _copy_supported(target_db, entry, source)
    for attachment in source.attachments:
        binary_id = target_db.add_binary(bytes(attachment.data), protected=True)
        entry.add_attachment(binary_id, attachment.filename)
    return entry


def _apply_plan(base: Any, source_b: Any, plan: MergePlan) -> None:
    for entry_uuid, item in plan.items.items():
        target = _find_entry(base, entry_uuid)
        source = _find_entry(source_b, entry_uuid)
        if item.resolution in {Resolution.KEEP_A, Resolution.IGNORE}:
            continue
        if item.resolution is Resolution.EXCLUDE:
            if target is not None:
                base.delete_entry(target)
            continue
        if source is None:
            raise SafeError("A planned source entry is no longer available.")
        if item.resolution is Resolution.KEEP_BOTH:
            _clone_entry(base, source, new_uuid=True)
        elif item.resolution is Resolution.USE_B:
            if target is not None:
                base.delete_entry(target)
            _clone_entry(base, source, new_uuid=False)
        elif item.resolution is Resolution.FIELD_MERGE:
            if target is None:
                raise SafeError("Field merge requires an entry in the base database.")
            chosen = {name for name, side in item.field_sources.items() if side == "B"}
            if not chosen <= MERGEABLE_FIELDS:
                raise SafeError("The plan contains a field that cannot be safely merged.")
            _copy_supported(base, target, source, chosen)


def execute_merge(
    session: SecureSession, comparison: ComparisonResult, plan: MergePlan, destination: Path
) -> Path:
    if plan.unresolved(comparison):
        raise SafeError("Every non-identical entry requires an explicit resolution before saving.")
    if any(
        e.status is Status.UNSUPPORTED
        and plan.items[e.uuid].resolution not in {Resolution.KEEP_A, Resolution.IGNORE}
        for e in comparison.entries
    ):
        raise SafeError("Entries with unsupported metadata can only be left unchanged.")
    output = validate_destination(session, destination)
    verify_inputs(session)
    temp_path: Path | None = None
    stage = "preparing the encrypted temporary output"
    try:
        handle, raw_path = tempfile.mkstemp(
            prefix=".secure-keepass-diff-", suffix=".kdbx", dir=output.parent
        )
        os.close(handle)
        temp_path = Path(raw_path)
        shutil.copyfile(session.path_a, temp_path)
        stage = "opening the encrypted temporary output"
        working = open_database(temp_path, session.credential_a)
        stage = "applying the merge plan"
        _apply_plan(working, session.db_b, plan)
        stage = "encrypting the merged database"
        working.save()
        del working
        verify_inputs(session)
        stage = "reopening the encrypted result for validation"
        validated = open_database(temp_path, session.credential_a)
        del validated
        stage = "publishing the validated output"
        os.replace(temp_path, output)
        temp_path = None
        verify_inputs(session)
        return output
    except SafeError:
        raise
    except Exception as exc:
        raise sanitize_error(exc, f"The operation failed while {stage}") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
