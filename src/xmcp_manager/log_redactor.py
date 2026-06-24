from __future__ import annotations

import re

SECRET_KEY_RE = re.compile(
    r"(?i)\b("
    r"X_BEARER_TOKEN|X_OAUTH_CONSUMER_SECRET|"
    r"oauth_token_secret|oauth_token|bearer_token|consumer_secret"
    r")\b\s*[:=]\s*([^\s,;]+)"
)
AUTH_HEADER_RE = re.compile(r"(?i)(Authorization\s*[:=]\s*)([^\n\r]+)")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")


def redact_line(line: str) -> str:
    line = SECRET_KEY_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", line)
    line = AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)}[REDACTED]", line)
    line = LONG_TOKEN_RE.sub("[REDACTED]", line)
    return line


def redact_text(text: str) -> str:
    return "\n".join(redact_line(line) for line in text.splitlines())
