"""PySide6 widgets application."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .comparison import compare_databases
from .errors import SafeError
from .loading import load_session
from .merge import MERGEABLE_FIELDS, execute_merge
from .models import ComparisonResult, MergePlan, PlanItem, Resolution, Status
from .planning import automatic_plan
from .session import DatabaseCredential, SecureSession
from .settings import SettingsStore


class WorkerSignals(QObject):
    success = Signal(object)
    failure = Signal(str)


class Worker(QRunnable):
    def __init__(self, operation: Any) -> None:
        super().__init__()
        self.operation = operation
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.success.emit(self.operation())
        except SafeError as exc:
            self.signals.failure.emit(str(exc))
        except Exception:
            self.signals.failure.emit("The operation failed. No secret details were recorded.")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Secure KeePass Diff")
        self.resize(1050, 680)
        self.pool = QThreadPool.globalInstance()
        self.session: SecureSession | None = None
        self.comparison: ComparisonResult | None = None
        self.plan = MergePlan()
        self.dirty = False
        self.settings = SettingsStore()
        self._build()
        self._load_settings()

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(
            QLabel(
                "A/base → new encrypted output, with only the changes you explicitly "
                "select from B. Neither original is modified."
            )
        )
        form = QFormLayout()
        self.a_path, self.b_path = QLineEdit(), QLineEdit()
        self.a_password, self.b_password = QLineEdit(), QLineEdit()
        self.a_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.b_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.a_key, self.b_key = QLineEdit(), QLineEdit()
        for label, widget, button_text, mode in (
            ("Database A (base)", self.a_path, "Browse…", "db"),
            ("A key file (optional)", self.a_key, "Browse…", "key"),
            ("Database B", self.b_path, "Browse…", "db"),
            ("B key file (optional)", self.b_key, "Browse…", "key"),
        ):
            row = QHBoxLayout()
            row.addWidget(widget)
            button = QPushButton(button_text)
            button.clicked.connect(lambda _=False, w=widget, m=mode: self._browse(w, m))
            row.addWidget(button)
            form.addRow(label, row)
        form.addRow("A master password", self.a_password)
        form.addRow("B master password", self.b_password)
        self.remember_paths = QCheckBox(
            "Remember database A/B paths on this device (never passwords or key files)"
        )
        self.remember_paths.toggled.connect(self._remember_toggled)
        form.addRow("Privacy", self.remember_paths)
        layout.addLayout(form)
        controls = QHBoxLayout()
        self.unlock = QPushButton("Unlock and Compare")
        self.unlock.clicked.connect(self._unlock)
        self.filter = QComboBox()
        self.filter.addItems(
            ["all", "changed", "only_a", "only_b", "unsupported", "resolved", "unresolved"]
        )
        self.filter.currentTextChanged.connect(self._populate)
        self.reset = QPushButton("Reset resolutions")
        self.reset.clicked.connect(self._reset)
        controls.addWidget(self.unlock)
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self.filter)
        controls.addWidget(self.reset)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Title", "Group A", "Group B", "Differences", "Newer hint", "Resolution"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        bottom = QHBoxLayout()
        self.summary = QLabel("Select two databases to begin.")
        self.save = QPushButton("Review and Save…")
        self.save.setEnabled(False)
        self.save.clicked.connect(self._save)
        bottom.addWidget(self.summary)
        bottom.addStretch()
        bottom.addWidget(self.save)
        layout.addLayout(bottom)
        self.setCentralWidget(root)

    def _browse(self, field: QLineEdit, mode: str) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select local file", "", "KeePass (*.kdbx)" if mode == "db" else "All files (*)"
        )
        if selected:
            field.setText(selected)

    def _load_settings(self) -> None:
        settings = self.settings.load()
        self.remember_paths.blockSignals(True)
        self.remember_paths.setChecked(settings.remember_paths)
        self.remember_paths.blockSignals(False)
        if settings.remember_paths:
            self.a_path.setText(settings.database_a)
            self.b_path.setText(settings.database_b)

    def _remember_toggled(self, enabled: bool) -> None:
        if not enabled:
            try:
                self.settings.disable()
            except OSError:
                QMessageBox.warning(
                    self,
                    "Settings not saved",
                    "The saved database paths could not be removed from the local config file.",
                )

    def _busy(self, active: bool) -> None:
        self.progress.setVisible(active)
        self.progress.setRange(0, 0 if active else 1)
        self.unlock.setEnabled(not active)

    def _unlock(self) -> None:
        self._clear_session()
        self._busy(True)
        acred = DatabaseCredential(
            self.a_password.text(), Path(self.a_key.text()) if self.a_key.text() else None
        )
        bcred = DatabaseCredential(
            self.b_password.text(), Path(self.b_key.text()) if self.b_key.text() else None
        )

        def operation() -> tuple[SecureSession, ComparisonResult]:
            session = load_session(Path(self.a_path.text()), acred, Path(self.b_path.text()), bcred)
            return session, compare_databases(session.db_a, session.db_b)

        worker = Worker(operation)
        worker.signals.success.connect(self._loaded)
        worker.signals.failure.connect(self._failed)
        self.pool.start(worker)

    def _loaded(self, result: object) -> None:
        session, comparison = cast(tuple[SecureSession, ComparisonResult], result)
        self.session = session
        self.comparison = comparison
        self.a_password.clear()
        self.b_password.clear()
        self.a_key.clear()
        self.b_key.clear()
        self.plan = automatic_plan(session, comparison)
        if self.remember_paths.isChecked():
            try:
                self.settings.save_paths(self.a_path.text(), self.b_path.text())
            except OSError:
                QMessageBox.warning(
                    self,
                    "Settings not saved",
                    "The databases were loaded, but their paths could not be saved.",
                )
        self._busy(False)
        self._populate()

    def _failed(self, message: str) -> None:
        self._busy(False)
        self._clear_session()
        QMessageBox.critical(self, "Operation failed", message)

    def _populate(self) -> None:
        if self.comparison is None:
            return
        mode = self.filter.currentText()
        rows = []
        for entry in self.comparison.entries:
            resolved = entry.uuid in self.plan.items
            if mode != "all" and not (
                (mode == "resolved" and resolved)
                or (mode == "unresolved" and not resolved and entry.status is not Status.IDENTICAL)
                or mode == entry.status.value
            ):
                continue
            rows.append(entry)
        self.table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            values = [
                entry.status.value,
                entry.title,
                "/".join(entry.group_a or ()),
                "/".join(entry.group_b or ()),
                ", ".join(d.name for d in entry.differences) or "—",
                entry.newer_hint,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            if entry.status in {Status.CHANGED, Status.UNSUPPORTED}:
                planned = self.plan.items.get(entry.uuid)
                expiry_only = planned is not None and {
                    difference.name for difference in entry.differences
                } <= {"expires", "expiry_time", "mtime", "atime"}
                if expiry_only:
                    self.table.setCellWidget(
                        row,
                        6,
                        QLabel("Automatically kept later expiration"),
                    )
                    continue
                button = QPushButton("Review side-by-side…")
                if entry.uuid in self.plan.items:
                    button.setText(
                        f"Resolved: {self.plan.items[entry.uuid].resolution.value} — review…"
                    )
                button.clicked.connect(
                    lambda _checked=False, u=entry.uuid: self._review_conflict(u)
                )
                self.table.setCellWidget(row, 6, button)
                continue
            combo = QComboBox()
            choices = self._choices(entry.status)
            combo.addItem("Choose explicitly…", None)
            for label, resolution in choices:
                combo.addItem(label, resolution.value)
            if entry.uuid in self.plan.items:
                wanted = self.plan.items[entry.uuid].resolution
                combo.setCurrentIndex(
                    next((i for i in range(combo.count()) if combo.itemData(i) == wanted.value), 0)
                )
            combo.currentIndexChanged.connect(
                lambda _i, u=entry.uuid, c=combo: self._resolve(u, c.currentData())
            )
            self.table.setCellWidget(row, 6, combo)
        unresolved = self.plan.unresolved(self.comparison)
        self.summary.setText(
            f"{len(self.comparison.entries)} entries; {len(unresolved)} unresolved "
            "blocking item(s). Password values remain masked."
        )
        self.save.setEnabled(not unresolved)

    @staticmethod
    def _choices(status: Status) -> list[tuple[str, Resolution]]:
        if status is Status.IDENTICAL:
            return [("Leave as base", Resolution.KEEP_A)]
        if status is Status.ONLY_A:
            return [
                ("Keep A in output", Resolution.KEEP_A),
                ("Exclude from output", Resolution.EXCLUDE),
            ]
        if status is Status.ONLY_B:
            return [("Import B into output", Resolution.USE_B), ("Ignore B", Resolution.IGNORE)]
        if status is Status.UNSUPPORTED:
            return [("Leave as base (required)", Resolution.KEEP_A)]
        return [
            ("Keep A", Resolution.KEEP_A),
            ("Use B", Resolution.USE_B),
            ("Keep both", Resolution.KEEP_BOTH),
            ("Choose supported fields from A/B…", Resolution.FIELD_MERGE),
        ]

    def _resolve(self, entry_uuid: Any, resolution: str | None) -> None:
        if resolution is None:
            self.plan = self.plan.reset(entry_uuid)
        else:
            self.plan = self.plan.resolve(PlanItem(entry_uuid, Resolution(resolution)))
        self.dirty = True
        self._populate()

    def _review_conflict(self, entry_uuid: Any) -> None:
        item = self._conflict_dialog(entry_uuid)
        if item is None:
            return
        self.plan = self.plan.resolve(item)
        self.dirty = True
        self._populate()

    def _conflict_dialog(self, entry_uuid: Any) -> PlanItem | None:
        assert self.comparison is not None
        assert self.session is not None
        entry = next(
            candidate for candidate in self.comparison.entries if candidate.uuid == entry_uuid
        )
        source_a = self.session.db_a.find_entries(uuid=entry_uuid, first=True)
        source_b = self.session.db_b.find_entries(uuid=entry_uuid, first=True)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Compare A and B — {entry.title}")
        dialog.resize(1100, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Compare each differing field. Timestamps are hints only. For field merge, "
                "select the source in the final column."
            )
        )
        if entry.warnings:
            warning = QLabel("Unsupported metadata: " + ", ".join(entry.warnings))
            warning.setWordWrap(True)
            layout.addWidget(warning)
        reveal = QCheckBox("Reveal password values in this dialog")
        layout.addWidget(reveal)
        table = QTableWidget(len(entry.differences), 4)
        table.setHorizontalHeaderLabels(
            ["Field", "Database A (base)", "Database B", "Output source"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setWordWrap(True)
        selectors: dict[str, QComboBox] = {}
        password_row: int | None = None
        for row, difference in enumerate(entry.differences):
            table.setItem(row, 0, QTableWidgetItem(difference.name))
            table.setItem(row, 1, QTableWidgetItem(difference.a_display))
            table.setItem(row, 2, QTableWidgetItem(difference.b_display))
            if difference.secret:
                password_row = row
            if difference.name in MERGEABLE_FIELDS and entry.status is Status.CHANGED:
                selector = QComboBox()
                selector.addItem("Use A", "A")
                selector.addItem("Use B", "B")
                existing = self.plan.items.get(entry_uuid)
                if existing and existing.resolution is Resolution.FIELD_MERGE:
                    selector.setCurrentIndex(
                        1 if existing.field_sources.get(difference.name) == "B" else 0
                    )
                selectors[difference.name] = selector
                table.setCellWidget(row, 3, selector)
            else:
                reason = (
                    "Unsupported: leave A unchanged"
                    if entry.status is Status.UNSUPPORTED
                    else "Whole-entry resolution only"
                )
                table.setItem(row, 3, QTableWidgetItem(reason))
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        layout.addWidget(table)

        def update_passwords(visible: bool) -> None:
            if password_row is None:
                return
            a_value = (source_a.password or "") if visible and source_a is not None else "••••••"
            b_value = (source_b.password or "") if visible and source_b is not None else "••••••"
            a_item = table.item(password_row, 1)
            b_item = table.item(password_row, 2)
            if a_item is not None:
                a_item.setText(a_value)
            if b_item is not None:
                b_item.setText(b_value)

        reveal.toggled.connect(update_passwords)
        actions = QDialogButtonBox()
        keep_a = actions.addButton("Keep complete A", QDialogButtonBox.ButtonRole.ActionRole)
        use_b = actions.addButton("Use complete B", QDialogButtonBox.ButtonRole.ActionRole)
        keep_both = actions.addButton("Keep both", QDialogButtonBox.ButtonRole.ActionRole)
        merge_fields = actions.addButton(
            "Apply field selections", QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel = actions.addButton(QDialogButtonBox.StandardButton.Cancel)
        if entry.status is Status.UNSUPPORTED:
            use_b.setEnabled(False)
            keep_both.setEnabled(False)
            merge_fields.setEnabled(False)
            use_b.setToolTip("PyKeePass cannot safely preserve this entry's unsupported metadata.")
        chosen: list[PlanItem] = []

        def choose(resolution: Resolution) -> None:
            chosen.append(PlanItem(entry_uuid, resolution))
            dialog.accept()

        keep_a.clicked.connect(lambda: choose(Resolution.KEEP_A))
        use_b.clicked.connect(lambda: choose(Resolution.USE_B))
        keep_both.clicked.connect(lambda: choose(Resolution.KEEP_BOTH))

        def choose_fields() -> None:
            sources = {name: str(selector.currentData()) for name, selector in selectors.items()}
            chosen.append(PlanItem(entry_uuid, Resolution.FIELD_MERGE, sources))
            dialog.accept()

        merge_fields.clicked.connect(choose_fields)
        cancel.clicked.connect(dialog.reject)
        layout.addWidget(actions)
        dialog.exec()
        reveal.setChecked(False)
        return chosen[0] if chosen else None

    def _reset(self) -> None:
        if self.session is not None and self.comparison is not None:
            self.plan = automatic_plan(self.session, self.comparison)
        else:
            self.plan = MergePlan()
        self.dirty = False
        self._populate()

    def _save(self) -> None:
        if self.session is None or self.comparison is None:
            return
        counts: dict[str, int] = {}
        for item in self.plan.items.values():
            counts[item.resolution.value] = counts.get(item.resolution.value, 0) + 1
        review = (
            "\n".join(f"{name}: {count}" for name, count in sorted(counts.items())) or "No changes"
        )
        if (
            QMessageBox.question(
                self,
                "Final review",
                f"Operations:\n{review}\n\nCreate and validate a new encrypted database?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Choose a new output", "", "KeePass (*.kdbx)")
        if not path:
            return
        session, comparison, plan = self.session, self.comparison, self.plan
        self._busy(True)
        worker = Worker(lambda: execute_merge(session, comparison, plan, Path(path)))
        worker.signals.success.connect(self._saved)
        worker.signals.failure.connect(self._failed)
        self.pool.start(worker)

    def _saved(self, output: object) -> None:
        self._busy(False)
        self.dirty = False
        QMessageBox.information(
            self,
            "Validated",
            f"The merged database was saved and reopened successfully:\n{output}",
            QMessageBox.StandardButton.Ok,
        )

    def _clear_session(self) -> None:
        if self.session:
            self.session.clear()
        self.session = None
        self.comparison = None
        self.plan = MergePlan()

    def closeEvent(self, event: Any) -> None:
        if (
            self.dirty
            and QMessageBox.question(
                self, "Discard choices?", "Close and discard unapplied resolution choices?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            event.ignore()
            return
        self._clear_session()
        event.accept()


def main() -> int:
    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
