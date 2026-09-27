from __future__ import annotations

from pathlib import Path

from secure_keepass_diff.settings import PathSettings, SettingsStore


def test_settings_are_opt_in_and_store_only_database_paths(tmp_path: Path):
    config = tmp_path / "settings" / "config.json"
    store = SettingsStore(config)
    assert store.load() == PathSettings()
    store.save_paths("C:/fake/a.kdbx", "C:/fake/b.kdbx")
    loaded = store.load()
    assert loaded == PathSettings(True, "C:/fake/a.kdbx", "C:/fake/b.kdbx")
    text = config.read_text(encoding="utf-8")
    assert "password" not in text.lower()
    assert "keyfile" not in text.lower()


def test_disabling_removes_remembered_paths(tmp_path: Path):
    config = tmp_path / "config.json"
    store = SettingsStore(config)
    store.save_paths("A", "B")
    store.disable()
    assert store.load() == PathSettings()
    text = config.read_text(encoding="utf-8")
    assert "database_a" not in text and "database_b" not in text


def test_invalid_config_fails_closed(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text("not-json", encoding="utf-8")
    assert SettingsStore(config).load() == PathSettings()
