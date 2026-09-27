# KDBX Merge Secure

[![Quality](https://github.com/acrimu/kdbx-merge-secure/actions/workflows/quality.yml/badge.svg)](https://github.com/acrimu/kdbx-merge-secure/actions/workflows/quality.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.txt)

An offline desktop application for securely comparing two KeePass KDBX databases, reviewing conflicts field by field, and creating a validated merged copy without modifying either original.

Database **A** is the base. The result starts as an encrypted copy of A and receives only the changes selected from **B**.

> [!IMPORTANT]
> This project is security-conscious, but it has not been independently audited. Keep verified backups and review the documented [security limitations](SECURITY.md) before using it with important databases.

## Features

- Native desktop interface built with PySide6—no browser, WebView, or local server.
- Completely offline runtime with no telemetry, analytics, update checks, or network features.
- Opens A and B with separate master passwords and optional key files.
- Matches entries by UUID, so duplicate titles are handled correctly.
- Shows changed fields side by side, including core fields, tags, custom properties, expiration, timestamps, icons, attachments, history indicators, and group hierarchy.
- Keeps passwords masked unless they are explicitly revealed in the comparison dialog.
- Supports **Keep A**, **Use B**, **Keep both**, and per-field A/B selection.
- Automatically keeps A-only entries and imports B-only entries; both choices remain editable.
- Automatically keeps the later value when expiration is the only substantive difference.
- Never writes to, renames, moves, or deletes either input database.
- Hashes both inputs and aborts if either changes during the session.
- Saves through an encrypted temporary KDBX, reopens it for validation, and atomically publishes the new output.
- Optionally remembers the last A/B paths—never passwords or key-file paths.

## Requirements

- Python 3.12 or newer. Python 3.14 is supported.
- Windows, macOS, or Linux where PySide6 and PyKeePass are supported.
- No administrator privileges.

The initial dependency installation may use the internet. The application itself is designed for offline use.

## Installation

Clone the repository and enter its directory:

```console
git clone https://github.com/acrimu/kdbx-merge-secure.git
cd kdbx-merge-secure
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-lock.txt
$env:PYTHONPATH="$PWD\src"
.\.venv\Scripts\python.exe -m secure_keepass_diff
```

If `python` is not recognized, install a supported Python release and enable the installer option that adds Python to `PATH`.

### macOS and Linux

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --require-hashes -r requirements-lock.txt
PYTHONPATH="$PWD/src" ./.venv/bin/python -m secure_keepass_diff
```

The runtime lock is fully pinned and hashed. Pip's `--require-hashes` option rejects unlisted or modified package artifacts.

## Subsequent launches

Windows PowerShell:

```powershell
cd C:\path\to\kdbx-merge-secure
$env:PYTHONPATH="$PWD\src"
.\.venv\Scripts\python.exe -m secure_keepass_diff
```

macOS or Linux:

```bash
cd /path/to/kdbx-merge-secure
PYTHONPATH="$PWD/src" ./.venv/bin/python -m secure_keepass_diff
```

## Usage

1. Select **Database A**, the base database.
2. Select **Database B**, the comparison database.
3. Enter each database's password and optional key file.
4. Select **Unlock and Compare**.
5. Review changed entries side by side and choose complete entries or individual fields from A and B.
6. Review the planned operations.
7. Choose a new `.kdbx` output filename and confirm the save.
8. Open the result using **Database A's password and key file**.

The output path must differ from both inputs and must not already exist. Success is reported only after the encrypted result has been reopened with A's credentials.

### Remembering database paths

Recent paths are disabled by default. Enabling **Remember database A/B paths** stores only those paths and a consent flag:

- Windows: `%APPDATA%\SecureKeePassDiff\config.json`
- Other platforms: `~/.config/SecureKeePassDiff/config.json` when `APPDATA` is unavailable

Passwords, key-file paths, decrypted entries, and diagnostics are never stored in this configuration. Disabling the option removes the remembered paths.

## Data-integrity design

The application does not mutate a loaded database while resolutions are selected. Choices are recorded in an explicit merge plan and applied only during output creation:

```text
Database A ──copy──> encrypted temporary KDBX ──apply plan──> reopen and validate
                                                                      │
Database B ───────────────selected fields and entries─────────────────┘
                                                                      │
                                                                      └──> new output KDBX
```

Input SHA-256 hashes are checked before and after the operation. The temporary output is created in the destination directory so the final rename can be atomic where supported by the filesystem.

## Security and limitations

Please read:

- [Security guidance](SECURITY.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Manual security-review checklist](docs/SECURITY_REVIEW.md)
- [Third-party license summary](THIRD_PARTY_LICENSES.md)

Important limitations include:

- Python cannot guarantee immediate or complete erasure of passwords and decrypted values from memory.
- A compromised operating system, runtime, dependency, debugger, keylogger, or screen recorder is outside the protection boundary.
- PyKeePass cannot losslessly recreate every KeePass feature. Exact preservation is not guaranteed for full history semantics, custom-icon payloads, auto-type associations, all timestamps, and plugin-specific XML.
- Unsupported metadata is surfaced rather than silently discarded. Entries with detected unsupported metadata can only be left unchanged in A.
- Atomic publication depends on the guarantees of the destination filesystem.

Always retain the original databases and verified backups until the merged output has been independently inspected in KeePass.

## Development

Install the separate, fully hashed development environment:

```powershell
python -m venv .venv-dev
.\.venv-dev\Scripts\python.exe -m pip install --require-hashes -r requirements-dev-lock.txt
$env:PYTHONPATH="$PWD\src"
```

Run all checks:

```powershell
.\.venv-dev\Scripts\python.exe -m pytest
.\.venv-dev\Scripts\python.exe -m ruff check .
.\.venv-dev\Scripts\python.exe -m ruff format --check .
.\.venv-dev\Scripts\python.exe -m mypy
```

Tests create synthetic KDBX files containing fake credentials only. See [Building and dependency workflow](docs/BUILDING.md) for lock regeneration, auditing, wheel creation, and desktop packaging guidance.

## Contributing

Bug reports and pull requests are welcome. Security reports and test cases must use synthetic databases and fake credentials—never attach a real KDBX database, key file, password, filesystem path, or decrypted diagnostic output.

Before submitting a pull request, run the complete test, Ruff, formatting, and mypy suite. Changes affecting persistence or merge behavior should include data-integrity and failure-path tests.

## License

The project source is available under the [MIT License](LICENSE.txt). Dependencies retain their own licenses; see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
