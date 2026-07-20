from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, set_tenant_context
from .models import ApiCredential, AuthSession, Tenant, User, utcnow

bearer = HTTPBearer(auto_error=False)


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    salt = os.urandom(16)
    rounds = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds_s, salt_s, digest_s = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _b64d(salt_s), int(rounds_s))
        return hmac.compare_digest(digest, _b64d(digest_s))
    except Exception:
        return False


def _encode_token(payload: dict) -> str:
    encoded = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64e(hmac.new(settings.secret_key.encode(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def create_session_token(db: Session, user: User, tenant: Tenant) -> str:
    """Create a server-revocable session and its signed access token."""
    now = utcnow()
    session = AuthSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        expires_at=now + timedelta(seconds=settings.token_ttl_seconds),
    )
    db.add(session)
    db.flush()
    payload = {
        "sub": user.id,
        "tenant": user.tenant_id,
        "role": user.role,
        "ver": user.token_version,
        "tver": tenant.security_version,
        "sid": session.id,
        "iat": int(now.timestamp()),
        "exp": int(session.expires_at.timestamp()),
        "nonce": secrets.token_hex(6),
    }
    return _encode_token(payload)


def decode_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64e(hmac.new(settings.secret_key.encode(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(_b64d(encoded))
        if int(payload["exp"]) <= int(time.time()):
            raise ValueError("Token expired")
        for required in ("sub", "tenant", "ver", "tver", "sid"):
            if required not in payload:
                raise ValueError(f"Missing {required}")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc


def revoke_session(db: Session, session_id: str, reason: str = "logout") -> bool:
    session = db.get(AuthSession, session_id)
    if not session or not session.active:
        return False
    session.active = False
    session.revoked_at = utcnow()
    session.revoke_reason = reason[:120]
    db.flush()
    return True


def _api_secret_hash(secret: str) -> str:
    return hmac.new(settings.secret_key.encode(), secret.encode(), hashlib.sha256).hexdigest()


def issue_api_credential_secret(credential: ApiCredential) -> str:
    secret = secrets.token_urlsafe(32)
    credential.key_prefix = secret[:8]
    credential.secret_hash = _api_secret_hash(secret)
    return f"ttk_{credential.id}.{secret}"


def _authenticate_api_credential(db: Session, token: str) -> "AuthContext":
    try:
        identifier, secret = token[4:].split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API credential") from exc
    credential = db.get(ApiCredential, identifier)
    now = utcnow()
    expires_at = None
    if credential and credential.expires_at:
        expires_at = (
            credential.expires_at
            if credential.expires_at.tzinfo
            else credential.expires_at.replace(tzinfo=timezone.utc)
        )
    supplied_hash = _api_secret_hash(secret)
    tenant = db.get(Tenant, credential.tenant_id) if credential else None
    if (
        credential is None
        or not credential.active
        or not hmac.compare_digest(credential.secret_hash, supplied_hash)
        or (expires_at is not None and expires_at <= now)
        or tenant is None
        or tenant.status != "active"
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API credential not available")
    try:
        scopes = tuple(sorted(set(json.loads(credential.scopes_json or "[]"))))
    except (TypeError, ValueError, json.JSONDecodeError):
        scopes = ()
    set_tenant_context(db, credential.tenant_id)
    return AuthContext(
        user_id=credential.id,
        tenant_id=credential.tenant_id,
        role=credential.role,
        email=f"api:{credential.name}",
        session_id=f"api:{credential.id}",
        principal_type="api_credential",
        scopes=scopes,
    )


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    tenant_id: str
    role: str
    email: str
    session_id: str
    principal_type: str = "user_session"
    scopes: tuple[str, ...] = ("*",)


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    token = credentials.credentials if credentials else request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if token.startswith("ttk_"):
        return _authenticate_api_credential(db, token)
    payload = decode_token(token)
    user = db.get(User, payload.get("sub"))
    tenant = db.get(Tenant, payload.get("tenant"))
    session = db.get(AuthSession, payload.get("sid"))
    now = utcnow()
    session_expires_at = (
        session.expires_at
        if session and session.expires_at.tzinfo
        else (session.expires_at.replace(tzinfo=timezone.utc) if session else now)
    )
    if (
        not user
        or not user.active
        or not tenant
        or tenant.status != "active"
        or user.tenant_id != tenant.id
        or user.tenant_id != payload.get("tenant")
        or user.token_version != payload.get("ver")
        or tenant.security_version != payload.get("tver")
        or not session
        or not session.active
        or session.user_id != user.id
        or session.tenant_id != tenant.id
        or session_expires_at <= now
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not available")
    set_tenant_context(db, tenant.id)
    return AuthContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
        session_id=session.id,
        principal_type="user_session",
        scopes=("*",),
    )


def require_admin(ctx: AuthContext = Depends(current_user)) -> AuthContext:
    if ctx.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return ctx


def require_reviewer(ctx: AuthContext = Depends(current_user)) -> AuthContext:
    if ctx.role not in {"admin", "reviewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required")
    if ctx.principal_type == "api_credential" and "review" not in ctx.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Review scope required")
    return ctx


def require_ingest(ctx: AuthContext = Depends(current_user)) -> AuthContext:
    if ctx.role not in {"admin", "reviewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required")
    if ctx.principal_type == "api_credential" and "ingest" not in ctx.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ingest scope required")
    return ctx
