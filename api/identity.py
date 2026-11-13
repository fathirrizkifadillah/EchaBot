from uuid import uuid4

from flask import session


OWNER_SESSION_KEY = "owner_id"


def current_owner_id() -> str:
    owner_id = session.get(OWNER_SESSION_KEY)
    if not owner_id:
        owner_id = uuid4().hex
        session[OWNER_SESSION_KEY] = owner_id
    return owner_id
