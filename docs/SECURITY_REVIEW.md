# Manual security review checklist

- Confirm source and dependency lock contain no unexplained network imports or endpoints.
- Install with `--require-hashes`; inspect package provenance, licenses, and vulnerability results.
- Run tests, Ruff, formatting, and mypy on a clean checkout.
- Exercise wrong credentials, corrupted files, key files, symlinks, same-file outputs, existing outputs, interrupted writes, and changed inputs using synthetic data.
- Monitor filesystem activity and confirm no plaintext temporary/config/log files are created.
- Monitor network activity and confirm zero runtime connections.
- Verify A and B are byte-identical before and after every scenario.
- Inspect merged entries, groups, UUIDs, attachments, custom fields, history, icons, auto-type, expiry, and timestamps in an independent KeePass client.
- Test close/reset/load-failure paths and observe that session references are released.
- Reassess all documented PyKeePass limitations before release.

