"""Sanitized application errors."""


class SafeError(Exception):
    """An error whose message is safe to display."""


def sanitize_error(exc: BaseException, context: str) -> SafeError:
    """Discard dependency messages, which may contain paths or decrypted values."""
    return SafeError(f"{context}. Check the selected file, credentials, and permissions.")
