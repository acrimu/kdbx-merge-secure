"""Immutable comparison and merge-plan models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from uuid import UUID


class Status(str, Enum):
    IDENTICAL = "identical"
    ONLY_A = "only_a"
    ONLY_B = "only_b"
    CHANGED = "changed"
    UNSUPPORTED = "unsupported"


class Resolution(str, Enum):
    KEEP_A = "keep_a"
    USE_B = "use_b"
    KEEP_BOTH = "keep_both"
    EXCLUDE = "exclude"
    IGNORE = "ignore"
    FIELD_MERGE = "field_merge"


@dataclass(frozen=True, slots=True)
class FieldDiff:
    name: str
    a_display: str
    b_display: str
    secret: bool = False


@dataclass(frozen=True, slots=True)
class ComparedEntry:
    uuid: UUID
    title: str
    group_a: tuple[str, ...] | None
    group_b: tuple[str, ...] | None
    status: Status
    differences: tuple[FieldDiff, ...] = ()
    newer_hint: str = "unknown"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    entries: tuple[ComparedEntry, ...]

    def counts(self) -> Mapping[Status, int]:
        return MappingProxyType({s: sum(e.status is s for e in self.entries) for s in Status})


@dataclass(frozen=True, slots=True)
class PlanItem:
    uuid: UUID
    resolution: Resolution
    field_sources: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolution", Resolution(self.resolution))
        object.__setattr__(self, "field_sources", MappingProxyType(dict(self.field_sources)))


@dataclass(frozen=True, slots=True)
class MergePlan:
    items: Mapping[UUID, PlanItem] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", MappingProxyType(dict(self.items)))

    def resolve(self, item: PlanItem) -> MergePlan:
        updated = dict(self.items)
        updated[item.uuid] = item
        return replace(self, items=updated)

    def reset(self, entry_uuid: UUID) -> MergePlan:
        updated = dict(self.items)
        updated.pop(entry_uuid, None)
        return replace(self, items=updated)

    def unresolved(self, comparison: ComparisonResult) -> tuple[ComparedEntry, ...]:
        blocking = {Status.CHANGED, Status.ONLY_A, Status.ONLY_B, Status.UNSUPPORTED}
        return tuple(
            e for e in comparison.entries if e.status in blocking and e.uuid not in self.items
        )


@dataclass(frozen=True, slots=True)
class EntrySnapshot:
    uuid: UUID
    title: str
    group_path: tuple[str, ...]
    username: str
    password: str
    url: str
    notes: str
    tags: tuple[str, ...]
    custom: Mapping[str, str]
    expires: bool
    expiry_time: datetime | None
    ctime: datetime | None
    mtime: datetime | None
    atime: datetime | None
    icon: int | None
    attachments: tuple[tuple[str, bytes], ...]
    history_count: int
    unsupported: tuple[str, ...] = ()
