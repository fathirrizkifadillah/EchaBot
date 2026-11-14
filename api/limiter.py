import re
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def get_rate_limit_key() -> str:
    """Return partition key for rate limiting.
    
    1. Authenticated users: partitioned by user ID.
    2. Guest users: partitioned by guest ID + remote IP (prevents quota exhaustion
       and protects against rotating guest IDs to bypass IP rate limits).
    3. Anonymous users: partitioned by remote IP address.
    """
    user_id = getattr(request, "auth_user_id", None)
    if user_id and _SAFE_ID_RE.match(str(user_id)):
        return f"user:{user_id}"

    guest_id = request.headers.get("X-Guest-Id")
    if guest_id and _SAFE_ID_RE.match(guest_id):
        return f"guest:{guest_id}:{get_remote_address()}"

    return get_remote_address()


limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[],
)
