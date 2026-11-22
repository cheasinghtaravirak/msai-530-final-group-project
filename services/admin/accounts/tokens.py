import time

import jwt
from django.conf import settings

from retail_common.auth import JWT_ALGORITHM, JWT_ISSUER

from .models import AppUser


def issue_token(user: AppUser) -> tuple[str, int, dict]:
    """Return (token, expires_in_seconds, claims) for a user, with their active role grants."""
    now = int(time.time())
    ttl = settings.JWT_TTL_SECONDS
    claims = {
        "iss": JWT_ISSUER,
        "sub": str(user.user_id),
        "name": user.full_name,
        "email": user.email,
        "roles": [g.as_claim() for g in user.active_grants().order_by("granted_at")],
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(claims, settings.JWT_PRIVATE_KEY, algorithm=JWT_ALGORITHM)
    return token, ttl, claims
