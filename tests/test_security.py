from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN = {"socket", "requests", "urllib", "httpx", "aiohttp", "ftplib", "smtplib", "websockets"}


def source_files() -> list[Path]:
    return list((Path(__file__).parents[1] / "src" / "secure_keepass_diff").glob("*.py"))


def test_application_does_not_import_networking_modules():
    violations = []
    for path in source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [alias.name.split(".")[0] for alias in node.names]
                if isinstance(node, ast.Import)
                else (
                    [node.module.split(".")[0]]
                    if isinstance(node, ast.ImportFrom) and node.module
                    else []
                )
            )
            if FORBIDDEN.intersection(names):
                violations.append(path.name)
    assert not violations


def test_no_remote_endpoints_or_telemetry_tokens():
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_files())
    assert "http://" not in combined and "https://" not in combined
    assert all(token not in combined for token in ("sentry_sdk", "telemetry", "analytics"))


def test_no_synthetic_secrets_written_outside_kdbx(tmp_path: Path):
    secrets = ("synthetic-A-master-only", "synthetic-B-master-only", "fake-entry-secret")
    for path in tmp_path.rglob("*"):
        if path.is_file() and path.suffix != ".kdbx":
            content = path.read_bytes()
            assert all(secret.encode() not in content for secret in secrets)
