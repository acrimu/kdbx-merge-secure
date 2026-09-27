# Security

## What is protected

The design prevents intentional runtime networking, plaintext exports, implicit output selection, writes to either input, partial final files, and silent unresolved merges. Passwords are masked and never logged. Inputs are SHA-256 checked before and after output creation. The output is not reported successful until PyKeePass reopens the encrypted temporary database with A's credentials.

Path persistence is disabled by default. With explicit in-app consent, the local JSON config contains only Database A and B paths plus the consent flag. It never contains passwords, key-file paths, entry data, or diagnostics. Disabling the option replaces the config with an opt-out record that contains no paths.

## What is not protected

This is not an audited product. It cannot protect data from a compromised operating system, Python runtime, GUI toolkit, dependency, screen recorder, debugger, malicious keylogger, filesystem administrator, memory/swap inspection, or backups made outside the program. Python strings and dependency objects may be copied by the runtime; clearing references shortens lifetimes but does **not** guarantee secure memory deletion. Atomic replacement also depends on filesystem guarantees.

## Dependency and offline risks

Installation can use the network. Runtime code contains no networking imports, endpoints, updater, or telemetry. Verify locked hashes with pip's `--require-hashes`; inspect vulnerability scan results before upgrades. A scanner requires network access to refresh advisory data, but the application never does. Dependency licenses are summarized in `THIRD_PARTY_LICENSES.md`; distributions must include the complete upstream license texts.

For defense in depth, run under an OS account without administrator rights and deny outbound connections for the Python/application executable with the host firewall. Test in an isolated VM when database sensitivity warrants it.

## Backups and recovery

Make verified, offline backups of both inputs before merging. Always choose a new destination. Open and inspect the result in KeePass before changing normal workflows. Retain originals until the result and its backup have been independently verified. Never use a production database for testing.

Security reports should contain only synthetic reproductions—never real database files, paths, credentials, entry values, key files, or decrypted diagnostics.

