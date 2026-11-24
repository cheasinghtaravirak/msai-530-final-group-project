"""Authentication and authorisation shared by every service.

The admin service issues RS256 JWTs. Every service verifies them locally with the public key
(settings.JWT_PUBLIC_KEY), so a running service keeps working even if Admin is down.

Claims: sub (user_id), name, email, roles: [{"role": "BRANCH_MANAGER", "branch_id": "BR-04"}], exp.
"""

import hmac
from dataclasses import dataclass, field
from typing import Any

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions, permissions

JWT_ISSUER = "retail-admin"
JWT_ALGORITHM = "RS256"

HQ_ADMIN = "HQ_ADMIN"
BRANCH_MANAGER = "BRANCH_MANAGER"
CASHIER = "CASHIER"
CUSTOMER = "CUSTOMER"  # reserved for Option B
STAFF_ROLES = (HQ_ADMIN, BRANCH_MANAGER, CASHIER)


@dataclass
class TokenUser:
    """The authenticated user, built from JWT claims. No database lookup."""

    id: str
    name: str = ""
    email: str = ""
    roles: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_hq_admin(self) -> bool:
        return any(g.get("role") == HQ_ADMIN for g in self.roles)

    def has_role(self, *roles: str, branch_id: str | None = None) -> bool:
        """True if the user holds one of `roles`, for `branch_id` if given.

        A grant with branch_id null (HQ_ADMIN) covers every branch.
        """
        for grant in self.roles:
            if grant.get("role") not in roles:
                continue
            if branch_id is None or grant.get("branch_id") in (None, branch_id):
                return True
        return False

    def branch_ids(self, *roles: str) -> set[str] | None:
        """Branches the user can act on with these roles. None means all branches."""
        result: set[str] = set()
        for grant in self.roles:
            if grant.get("role") not in roles:
                continue
            if grant.get("branch_id") is None:
                return None
            result.add(grant["branch_id"])
        return result


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.JWT_PUBLIC_KEY,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        options={"require": ["exp", "sub", "iss"]},
    )


class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("latin-1")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != "Bearer":
            raise exceptions.AuthenticationFailed("Authorization header must be: Bearer <token>")
        try:
            claims = decode_token(parts[1])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token expired", code="token_expired") from None
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Invalid token", code="invalid_token") from None
        user = TokenUser(
            id=claims["sub"],
            name=claims.get("name", ""),
            email=claims.get("email", ""),
            roles=claims.get("roles", []),
        )
        return user, claims

    def authenticate_header(self, request) -> str:
        # Makes DRF answer 401 (not 403) when credentials are missing.
        return "Bearer"


def _find_branch_id(request, view, name: str) -> str | None:
    sources = [
        (view.kwargs or {}).get(name) if hasattr(view, "kwargs") else None,
        request.query_params.get(name),
        request.data.get(name) if isinstance(request.data, dict) else None,
    ]
    found = {value for value in sources if value is not None}
    if len(found) > 1:
        # The view may act on a different source than the one checked here, so a mismatch is refused.
        raise exceptions.PermissionDenied(f"{name} differs between the URL, query string and body")
    return found.pop() if found else None


def HasRole(*roles: str, branch_from: str | None = None):  # noqa: N802 - reads like a class
    """Permission class factory.

        permission_classes = [HasRole(HQ_ADMIN, BRANCH_MANAGER, branch_from="branch_id")]

    With `branch_from`, the branch is read from the URL kwargs, query string or body, and the
    user must hold one of the roles for that branch.
    """

    class _HasRole(permissions.BasePermission):
        message = f"Requires role: {', '.join(roles)}"

        def has_permission(self, request, view) -> bool:
            user = request.user
            if not getattr(user, "is_authenticated", False) or not isinstance(user, TokenUser):
                return False
            if branch_from is None:
                return user.has_role(*roles)
            branch_id = _find_branch_id(request, view, branch_from)
            if branch_id is None:
                return user.has_role(*roles)
            return user.has_role(*roles, branch_id=branch_id)

    _HasRole.__name__ = f"HasRole({','.join(roles)})"
    return _HasRole


def require_branch_access(request, branch_id: str, *roles: str) -> None:
    """Raise 403 unless the user holds one of `roles` for `branch_id`."""
    user = request.user
    if not isinstance(user, TokenUser) or not user.has_role(*roles, branch_id=branch_id):
        raise exceptions.PermissionDenied(f"No access to branch {branch_id}")


class IsInternalService(permissions.BasePermission):
    """For /internal/* endpoints: the caller must send X-Service-Token."""

    message = "Internal endpoint"

    def has_permission(self, request, view) -> bool:
        expected = getattr(settings, "SERVICE_TOKEN", "")
        given = request.headers.get("X-Service-Token", "")
        return bool(expected) and hmac.compare_digest(given, expected)
