"""Minimal, non-secret local settings persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PathSettings:
    remember_paths: bool = False
    database_a: str = ""
    database_b: str = ""


class SettingsStore:
    """Persist explicit path consent without ever accepting secret values."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self._default_path()

    @staticmethod
    def _default_path() -> Path:
        base = Path(os.environ.get("APPDATA", Path.home() / ".config"))
        return base / "SecureKeePassDiff" / "config.json"

    def load(self) -> PathSettings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return PathSettings()
        if not isinstance(raw, dict) or raw.get("remember_paths") is not True:
            return PathSettings()
        a = raw.get("database_a", "")
        b = raw.get("database_b", "")
        return PathSettings(True, a if isinstance(a, str) else "", b if isinstance(b, str) else "")

    def save_paths(self, database_a: str, database_b: str) -> None:
        """Save database paths only; callers cannot pass credentials or key files."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = {
            "remember_paths": True,
            "database_a": database_a,
            "database_b": database_b,
        }
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def disable(self) -> None:
        """Persist opt-out and remove previously remembered paths."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text('{"remember_paths": false}\n', encoding="utf-8")
        temporary.replace(self.path)
