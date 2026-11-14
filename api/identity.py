"""
Identity resolver: returns the current user's owner ID.

When JWT auth is active (Authorization header present), returns the authenticated
user ID. Falls back to anonymous session-based owner for backwards compatibility.
"""

from uuid import uuid4

from flask import request, session


OWNER_SESSION_KEY = "owner_id"


def current_owner_id() -> str:
    """Return the authenticated user ID, or an anonymous session-based ID."""
    # JWT-authenticated user (set by require_auth decorator or middleware)
    user_id = getattr(request, "auth_user_id", None)
    if user_id:
        return user_id

    # Legacy anonymous mode
    owner_id = session.get(OWNER_SESSION_KEY)
    if not owner_id:
        owner_id = uuid4().hex
        session[OWNER_SESSION_KEY] = owner_id
    return owner_id
