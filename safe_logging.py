"""Small, deterministic redaction helpers for operator-facing logs."""

import logging
import re


_SENSITIVE_QUERY = re.compile(
    r"([?&](?:access_token|refresh_token|token|code|signature|sig|key|pin|password)=)[^&#\s\"]*",
    re.IGNORECASE,
)
_AUTHORIZATION = re.compile(
    r"(authorization\s*[:=]\s*)(?:bearer|basic)\s+[^\s,}\]]+",
    re.IGNORECASE,
)
_SENSITIVE_FIELD = re.compile(
    r"(authorization|access_token|refresh_token|dpop(?:[_-]private[_-]key)?|password|pin|cookie|token|code)"
    r"(\s*[:=]\s*)((?!\[REDACTED\])[^,\s}\]]+)",
    re.IGNORECASE,
)


def redact_sensitive(value: object) -> str:
    """Redact common credential-bearing fields while preserving diagnostics."""
    text = str(value)
    text = _AUTHORIZATION.sub(r"\1[REDACTED]", text)
    text = _SENSITIVE_QUERY.sub(r"\1[REDACTED]", text)
    return _SENSITIVE_FIELD.sub(r"\1\2[REDACTED]", text)


class RedactingFormatter(logging.Formatter):
    """Formatter that applies redaction to every rendered log message."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive(super().format(record))
