"""
Identity resolver: returns the current user's owner ID.

When JWT auth is active (Authorization header present), returns the authenticated
user ID. Supports validated X-Guest-Id header for guest mode with strong isolation.
Falls back to anonymous session-based owner for backwards compatibility.
"""

import re
from uuid import uuid4

from flask import request, session

OWNER_SESSION_KEY = "owner_id"

# Strict pattern for UUIDv4 (with hyphens) or 32-hex character ID
_VALID_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_VALID_HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def sanitize_guest_id(guest_id: str | None) -> str | None:
    """Validate and sanitize a client-provided guest ID.
    
    Rejects any string that is not a strict 36-char UUID or 32-char hex string,
    preventing path traversal, SQL injection, or namespace collisions.
    """
    if not guest_id or not isinstance(guest_id, str):
        return None
    trimmed = guest_id.strip()
    if _VALID_UUID_RE.match(trimmed) or _VALID_HEX32_RE.match(trimmed):
        cleaned = trimmed.lower().replace("-", "")
        return f"guest_{cleaned}"
    return None


def current_owner_id() -> str:
    """Return the authenticated user ID, validated guest ID, or session-based ID."""
    # 1. JWT-authenticated user (set by require_auth decorator or middleware)
    user_id = getattr(request, "auth_user_id", None)
    if user_id:
        return user_id

    # 2. Guest Mode: client provides a persistent per-device UUID in X-Guest-Id
    guest_header = request.headers.get("X-Guest-Id")
    sanitized_guest = sanitize_guest_id(guest_header)
    if sanitized_guest:
        return sanitized_guest

    # 3. Legacy anonymous session mode
    owner_id = session.get(OWNER_SESSION_KEY)
    if not owner_id:
        owner_id = uuid4().hex
        session[OWNER_SESSION_KEY] = owner_id
    return owner_id


def is_guest_owner(owner_id: str | None = None) -> bool:
    """Check if the given (or current) owner ID is an unauthenticated guest."""
    oid = owner_id or current_owner_id()
    return oid.startswith("guest_")
