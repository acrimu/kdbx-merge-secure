"""Safe automatic merge-plan rules explicitly requested by the user."""

from __future__ import annotations

from .models import ComparisonResult, MergePlan, PlanItem, Resolution, Status
from .session import SecureSession


def automatic_plan(session: SecureSession, comparison: ComparisonResult) -> MergePlan:
    """Apply the explicitly requested safe automatic resolution rules.

    Entries found only in A are retained and entries found only in B are imported.
    Modification and access timestamps are ignored for this narrow rule because changing an
    expiry commonly changes them. Every substantive entry field must otherwise compare equal.
    A non-expiring entry is treated as later than a finite expiry.
    """
    plan = MergePlan()
    allowed = {"expires", "expiry_time", "mtime", "atime"}
    expiry_fields = {"expires", "expiry_time"}
    for compared in comparison.entries:
        if compared.status is Status.ONLY_A:
            plan = plan.resolve(PlanItem(compared.uuid, Resolution.KEEP_A))
            continue
        if compared.status is Status.ONLY_B:
            plan = plan.resolve(PlanItem(compared.uuid, Resolution.USE_B))
            continue
        names = {difference.name for difference in compared.differences}
        if (
            compared.status is not Status.CHANGED
            or not names.intersection(expiry_fields)
            or not names <= allowed
        ):
            continue
        entry_a = session.db_a.find_entries(uuid=compared.uuid, first=True)
        entry_b = session.db_b.find_entries(uuid=compared.uuid, first=True)
        if entry_a is None or entry_b is None:
            continue
        if not entry_a.expires:
            plan = plan.resolve(PlanItem(compared.uuid, Resolution.KEEP_A))
        elif not entry_b.expires:
            plan = plan.resolve(
                PlanItem(
                    compared.uuid,
                    Resolution.FIELD_MERGE,
                    {"expires": "B", "expiry_time": "B"},
                )
            )
        elif entry_a.expiry_time is not None and entry_b.expiry_time is not None:
            if entry_b.expiry_time > entry_a.expiry_time:
                plan = plan.resolve(
                    PlanItem(
                        compared.uuid,
                        Resolution.FIELD_MERGE,
                        {"expires": "B", "expiry_time": "B"},
                    )
                )
            else:
                plan = plan.resolve(PlanItem(compared.uuid, Resolution.KEEP_A))
    return plan
