"""GitHub webhook signature validation (HMAC SHA-256 of payload)."""
from __future__ import annotations

import hashlib
import hmac

from app.config import settings


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Validate `X-Hub-Signature-256` header.

    The header format is `sha256=<hex digest>`. Returns False on missing /
    malformed headers · constant-time compare on match.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = (
        "sha256="
        + hmac.new(
            settings.github_webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)
