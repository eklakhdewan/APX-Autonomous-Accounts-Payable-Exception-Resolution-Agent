from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Union

SENSITIVE_KEYS: Set[str] = {
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "client_id",
    "id_token",
    "jwt",
    "bearer",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "cookie",
    "set-cookie",
    "csrf",
    "xsrf",
    "session",
    "ssn",
    "social_security",
    "credit_card",
    "creditcard",
    "card_number",
    "cardnumber",
    "cvv",
    "cvc",
    "pin",
    "private_key",
    "privatekey",
    "secret_key",
    "secretkey",
    "aws_secret",
    "aws_access",
    "gcp_key",
    "azure_key",
}

SENSITIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),  # Credit card numbers
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email (optional)
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),  # Bearer tokens
    re.compile(r"sk-[A-Za-z0-9]{32,}"),  # OpenAI-style API keys
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),  # Slack tokens
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),  # GitHub tokens
    re.compile(r"api[_-]?key[_-]?[A-Za-z0-9]{16,}"),  # Generic API keys
]


def is_sensitive_key(key: str) -> bool:
    """Check if a key name indicates sensitive data."""
    key_lower = key.lower().replace("-", "_").replace(" ", "_")
    # Use exact matching or word-boundary-aware matching to avoid false positives
    # like "tokens" matching "token"
    for sensitive in SENSITIVE_KEYS:
        if sensitive == key_lower:
            return True
        # Check for word boundaries: sensitive_key, key_sensitive, sensitive-key, etc.
        if f"_{sensitive}_" in f"_{key_lower}_":
            return True
        if f"-{sensitive}-" in f"-{key_lower}-":
            return True
        if key_lower.startswith(f"{sensitive}_") or key_lower.startswith(f"{sensitive}-"):
            return True
        if key_lower.endswith(f"_{sensitive}") or key_lower.endswith(f"-{sensitive}"):
            return True
    return False


def redact_value(value: Any, max_visible: int = 4) -> str:
    """Redact a sensitive value, showing only prefix/suffix."""
    if value is None:
        return "***"
    s = str(value)
    if len(s) <= max_visible * 2:
        return "*" * len(s)
    return s[:max_visible] + "*" * (len(s) - max_visible * 2) + s[-max_visible:]


def redact_dict(data: Dict[str, Any], max_visible: int = 4) -> Dict[str, Any]:
    """Recursively redact sensitive keys in a dictionary."""
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if is_sensitive_key(key):
            result[key] = redact_value(value, max_visible)
        elif isinstance(value, dict):
            result[key] = redact_dict(value, max_visible)
        elif isinstance(value, list):
            result[key] = [redact_dict(item, max_visible) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


def redact_string(text: str) -> str:
    """Redact sensitive patterns in a string."""
    if not text:
        return text
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(lambda m: "*" * len(m.group()), result)
    return result


def deep_redact(obj: Any, max_visible: int = 4) -> Any:
    """Deep redact any JSON-serializable object."""
    if isinstance(obj, dict):
        return redact_dict(obj, max_visible)
    elif isinstance(obj, list):
        return [deep_redact(item, max_visible) for item in obj]
    elif isinstance(obj, str):
        return redact_string(obj)
    return obj


def redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Redact sensitive headers."""
    return {k: redact_value(v) if is_sensitive_key(k) else v for k, v in headers.items()}