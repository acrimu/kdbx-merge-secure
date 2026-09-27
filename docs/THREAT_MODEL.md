# Threat model

## Assets and trust boundaries

Assets are master credentials, key-file paths and contents, decrypted entry data, encrypted input bytes, and the integrity of the merged output. The local process, PySide6, PyKeePass, lxml, cryptographic libraries, Python, the OS, and the filesystem are trusted dependencies. Database B is untrusted structured input.

## Threats and controls

| Threat | Control |
|---|---|
| Accidental overwrite of A or B | Canonical/same-file comparison, new-file-only policy, no save calls on loaded inputs |
| Partial or invalid result | Encrypted same-directory temporary copy, reopen validation, atomic rename |
| Inputs change during the session | SHA-256 captured at load and verified before and after merge |
| Wrong-direction/destructive merge | A is visibly fixed as base; immutable plan; explicit resolution for every non-identical item |
| Secret disclosure in UI/errors/logs | Masked password fields, fixed sanitized errors, no logging or clipboard support |
| Runtime exfiltration | No networking imports/endpoints; AST security checks; firewall guidance |
| Metadata loss | Unsupported state is blocking; documented PyKeePass preservation limits |
| Resource exhaustion/malformed KDBX | Work is off the GUI thread; dependency parser limits apply; failure is sanitized and temp is cleaned |

## Residual risk

Memory cannot be reliably wiped in Python. File hashes detect change, not a malicious replacement with an identical digest. Symlink and network filesystems may weaken path/atomicity assumptions. A compromised dependency or OS defeats application controls. Side channels and user screenshots remain out of scope.

