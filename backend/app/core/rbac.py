"""Role-Based Access Control (RBAC) and Identity Module for Air-Gapped Operations.

Implements defence-grade access control enforcing the separation of duties:
- Operator: Uploads source files, triggers understanding, generates deliverables, requests approval.
            Strictly prohibited from approving, rejecting, or exporting safety-critical assets (HTTP 403).
- Reviewer / Approver: Reviews generated deliverables against source citations, approves or rejects,
                       and authorizes export.
- Admin: Full system oversight and administration.

Supports both HMAC-SHA256 signed JWT tokens and explicit X-User-Role / X-User-Id headers.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

logger = logging.getLogger("app.core.rbac")

security_bearer = HTTPBearer(auto_error=False)


class Role(str, Enum):
    """Enclave operational roles."""

    OPERATOR = "operator"
    REVIEWER = "reviewer"
    APPROVER = "approver"  # Alias for reviewer
    ADMIN = "admin"


class Permission(str, Enum):
    """Granular operational permissions."""

    UPLOAD = "upload"
    PROCESS = "process"
    RETRIEVE = "retrieve"
    TRACE = "trace"
    GENERATE = "generate"
    REQUEST_APPROVAL = "request_approval"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    EDIT = "edit"
    AUDIT_VIEW = "audit_view"
    VIEW = "view"
    ADMIN = "admin"


# Role -> Permissions Mapping
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    Role.OPERATOR.value: {
        Permission.UPLOAD,
        Permission.PROCESS,
        Permission.RETRIEVE,
        Permission.TRACE,
        Permission.GENERATE,
        Permission.REQUEST_APPROVAL,
        Permission.EDIT,
        Permission.VIEW,
    },
    Role.REVIEWER.value: {
        Permission.VIEW,
        Permission.RETRIEVE,
        Permission.TRACE,
        Permission.REQUEST_APPROVAL,
        Permission.EDIT,
        Permission.APPROVE,
        Permission.REJECT,
        Permission.EXPORT,
        Permission.AUDIT_VIEW,
    },
    Role.APPROVER.value: {
        Permission.VIEW,
        Permission.RETRIEVE,
        Permission.TRACE,
        Permission.REQUEST_APPROVAL,
        Permission.EDIT,
        Permission.APPROVE,
        Permission.REJECT,
        Permission.EXPORT,
        Permission.AUDIT_VIEW,
    },
    Role.ADMIN.value: {
        Permission.UPLOAD,
        Permission.PROCESS,
        Permission.RETRIEVE,
        Permission.TRACE,
        Permission.GENERATE,
        Permission.REQUEST_APPROVAL,
        Permission.EDIT,
        Permission.APPROVE,
        Permission.REJECT,
        Permission.EXPORT,
        Permission.AUDIT_VIEW,
        Permission.VIEW,
        Permission.ADMIN,
    },
}



@dataclass
class UserContext:
    """Authenticated user context containing identity, role, and granted permissions."""

    user_id: str
    role: str
    permissions: set[Permission]

    def has_permission(self, permission: Permission) -> bool:
        """Check if this user has the required permission or admin superuser rights."""
        if Permission.ADMIN in self.permissions or self.role == Role.ADMIN.value:
            return True
        return permission in self.permissions

    def has_role(self, *roles: Role | str) -> bool:
        """Check if the user matches any of the specified roles."""
        for r in roles:
            r_val = r.value if isinstance(r, Role) else r
            if self.role == r_val:
                return True
            if r_val in (Role.REVIEWER.value, Role.APPROVER.value) and self.role in (
                Role.REVIEWER.value,
                Role.APPROVER.value,
            ):
                return True
            if self.role == Role.ADMIN.value:
                return True
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data_str: str) -> bytes:
    padding = 4 - (len(data_str) % 4)
    if padding != 4:
        data_str += "=" * padding
    return base64.urlsafe_b64decode(data_str)


def create_access_token(user_id: str, role: str, expires_in: int = 86400) -> str:
    """Create a self-contained HMAC-SHA256 signed JWT token."""
    settings = get_settings()
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role.lower(),
        "iat": now,
        "exp": now + expires_in,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    key = settings.SECRET_KEY.encode("utf-8")
    signature = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify HMAC-SHA256 signature and token expiry, returning decoded claims."""
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token structure.",
        )

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")

    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature encoding.",
        ) from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature (verification failed).",
        )

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        ) from exc

    exp = payload.get("exp")
    if exp and int(time.time()) > exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
        )

    return payload


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UserContext:
    """Resolve user context from either Bearer JWT or explicit headers.

    Fallback defaults to 'operator' in local enclave when unauthenticated,
    while strictly rejecting unrecognized or tampered roles.
    """
    user_id: str = "operator_default"
    role_str: str = Role.OPERATOR.value

    # 1. Inspect Bearer token if provided
    if bearer and bearer.credentials:
        claims = verify_access_token(bearer.credentials)
        user_id = str(claims.get("sub", "unknown_user"))
        role_str = str(claims.get("role", Role.OPERATOR.value)).lower()
    # 2. Inspect X-User-Role / X-User-Id headers if provided
    elif x_user_role:
        role_str = x_user_role.strip().lower()
        user_id = x_user_id.strip() if x_user_id else f"{role_str}_user"
    elif x_user_id:
        user_id = x_user_id.strip()

    # Normalize approver -> reviewer
    if role_str == Role.APPROVER.value:
        role_str = Role.REVIEWER.value

    # Validate role existence
    if role_str not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown or unauthorized role: '{role_str}'. Valid roles: {[r.value for r in Role]}",
        )

    perms = ROLE_PERMISSIONS.get(role_str, set())
    return UserContext(user_id=user_id, role=role_str, permissions=perms)


def require_permission(permission: Permission):
    """FastAPI dependency enforcing that the caller possesses a specific permission."""

    async def _permission_dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not user.has_permission(permission):
            logger.warning(
                "Access forbidden: User '%s' (role: '%s') attempted action requiring permission '%s'",
                user.user_id,
                user.role,
                permission.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Forbidden",
                    "user_id": user.user_id,
                    "role": user.role,
                    "required_permission": permission.value,
                    "message": (
                        f"Access denied: User '{user.user_id}' with role '{user.role}' lacks "
                        f"mandatory permission '{permission.value}'."
                    ),
                },
            )
        return user

    return _permission_dependency


def require_role(*allowed_roles: Role | str):
    """FastAPI dependency enforcing that the caller belongs to one of the specified roles."""

    async def _role_dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not user.has_role(*allowed_roles):
            allowed_names = [r.value if isinstance(r, Role) else r for r in allowed_roles]
            logger.warning(
                "Access forbidden: User '%s' (role: '%s') lacks required role in %s",
                user.user_id,
                user.role,
                allowed_names,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Forbidden",
                    "user_id": user.user_id,
                    "role": user.role,
                    "allowed_roles": allowed_names,
                    "message": f"Access denied: Role '{user.role}' not permitted. Required: {allowed_names}",
                },
            )
        return user

    return _role_dependency
