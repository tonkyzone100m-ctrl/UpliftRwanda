"""JWT authentication for the UpliftRwanda ministerial (admin) surface.

Design contract
    -  ALL analytics/insights/simulation GET routes stay 100% public.
    -  Only administrative write/upload routes (e.g. POST /api/admin/seed)
       require a Bearer access token issued by POST /api/auth/login.
    -  Passwords are stored ONLY as bcrypt hashes; plaintext is never kept.
    -  Tokens are HS256 JWTs (5-minute-clock skew, verified issuer/subject).

Configuration (environment variables, read at process start)
    UPLIFT_ADMIN_USERNAME     default "nisr_admin"
    UPLIFT_ADMIN_PASSWORD     plaintext -> converted to a bcrypt hash at
                              startup and kept in memory only
    UPLIFT_ADMIN_PASSWORD_HASH  bcrypt hash; wins over the plaintext option
    UPLIFT_JWT_SECRET         HS256 signing secret. If unset, an ephemeral
                              random secret is generated per boot (safer than
                              a weak committed default): every restart
                              invalidates outstanding sessions.
    UPLIFT_TOKEN_TTL_MINUTES  access-token lifetime, default 120

Fallback dev password when neither env var is set: "nisr-admin-2026"
(so a fresh clone boots with working credentials; the API logs a loud
warning whenever it is active).
"""

import hmac
import logging
import os
import secrets
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel, Field

logger = logging.getLogger("uplift_auth")

DEV_FALLBACK_PASSWORD = "nisr-admin-2026"
ISSUER = "uplift-rwanda-api"
_TOKEN_KIND = "access"
_MAX_FAILED_LOGINS = 5
_FAILURE_WINDOW_SECONDS = 60.0


def _hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))


class AuthConfig:
    """Immutable-at-boot configuration; settings resolved once, never logged."""

    def __init__(self):
        self.admin_username = os.getenv("UPLIFT_ADMIN_USERNAME", "nisr_admin")
        env_hash = os.getenv("UPLIFT_ADMIN_PASSWORD_HASH")
        if os.getenv("UPLIFT_ADMIN_PASSWORD"):
            self.admin_password_hash = _hash_password(os.getenv("UPLIFT_ADMIN_PASSWORD"))
            logger.info("Admin password loaded from UPLIFT_ADMIN_PASSWORD (bcrypt-hashed in memory).")
        elif env_hash:
            try:
                bcrypt.checkpw(b"probe", env_hash.encode("utf-8"))
            except ValueError as exc:
                raise RuntimeError(f"UPLIFT_ADMIN_PASSWORD_HASH is not a valid bcrypt hash: {exc}") from exc
            self.admin_password_hash = env_hash.encode("utf-8")
            logger.info("Admin password hash loaded from UPLIFT_ADMIN_PASSWORD_HASH.")
        else:
            self.admin_password_hash = _hash_password(DEV_FALLBACK_PASSWORD)
            logger.warning(
                "No UPLIFT_ADMIN_PASSWORD(=_HASH) set - using fallback dev password "
                "for 'nisr_admin'. Set UPLIFT_ADMIN_PASSWORD (or the HASH variant) "
                "before any real deployment."
            )
        self.jwt_secret = os.getenv("UPLIFT_JWT_SECRET") or secrets.token_urlsafe(48)
        if not os.getenv("UPLIFT_JWT_SECRET"):
            logger.warning(
                "No UPLIFT_JWT_SECRET configured - sessions expire on every restart. "
                "Export a persistent random secret in production."
            )
        self.ttl_minutes = int(os.getenv("UPLIFT_TOKEN_TTL_MINUTES", "120"))

    @property
    def ttl_seconds(self) -> int:
        return self.ttl_minutes * 60


CONFIG = AuthConfig()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


_FAILED_LOGINS = {}
_RATE_LIMITED_NOW = set()


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _register_failed_attempt(request: Request) -> None:
    key = _client_key(request)
    now = time.monotonic()
    window = _FAILED_LOGINS.setdefault(key, deque())
    while window and now - window[0] > _FAILURE_WINDOW_SECONDS:
        window.popleft()
    window.append(now)
    _RATE_LIMITED_NOW.add(key)


def _clear_failures(request: Request) -> None:
    _FAILED_LOGINS.pop(_client_key(request), None)
    _RATE_LIMITED_NOW.discard(_client_key(request))


def _is_rate_limited(request: Request) -> bool:
    key = _client_key(request)
    if key in _RATE_LIMITED_NOW:
        window = _FAILED_LOGINS.get(key)
        if window:
            now = time.monotonic()
            if now - window[-1] < _FAILURE_WINDOW_SECONDS and len(window) >= _MAX_FAILED_LOGINS:
                return True
        _RATE_LIMITED_NOW.discard(key)
        if window is None or not window:
            _FAILED_LOGINS.pop(key, None)
    return False


def reset_rate_limiter() -> None:
    """Test hook: wipes in-memory brute-force state."""
    _FAILED_LOGINS.clear()
    _RATE_LIMITED_NOW.clear()


def verify_credentials(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(CONFIG.admin_username.encode("utf-8"), username.strip().lower().encode("utf-8"))
    pass_ok = False
    try:
        pass_ok = bcrypt.checkpw(password.encode("utf-8"), CONFIG.admin_password_hash)
    except ValueError:
        pass_ok = False
    return user_ok and pass_ok


def issue_access_token(username: str) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=CONFIG.ttl_minutes)
    token = jwt.encode(
        {
            "sub": username,
            "iss": ISSUER,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "kind": _TOKEN_KIND,
        },
        CONFIG.jwt_secret,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": CONFIG.ttl_seconds,
        "expires_at": int(expires.timestamp()),
        "username": username,
    }


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        CONFIG.jwt_secret,
        algorithms=["HS256"],
        issuer=ISSUER,
        options={"require": ["sub", "exp"]},
        leeway=5,
    )


def get_current_admin(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    scheme, credentials = get_authorization_scheme_param(auth_header)
    if scheme.lower() != "bearer" or not credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "code": "not_authenticated",
                "detail": "Ministerial actions require an administrator session. Sign in first.",
            },
        )
    try:
        claims = decode_access_token(credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "code": "token_expired", "detail": "Session expired. Sign in again."},
        ) from None
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "code": "invalid_token", "detail": "Invalid access token."},
        ) from exc
    if claims.get("kind") != _TOKEN_KIND or claims.get("sub") != CONFIG.admin_username:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "code": "invalid_token", "detail": "Token is not valid for admin actions."},
        )
    return {"username": claims["sub"], "exp": claims["exp"]}


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/login")
def login(payload: LoginRequest, request: Request):
    """Exchange admin credentials for a short-lived JWT access token."""
    if _is_rate_limited(request):
        raise HTTPException(
            status_code=429,
            detail={
                "status": "error",
                "code": "too_many_attempts",
                "detail": "Too many failed sign-in attempts. Try again in about a minute.",
            },
        )
    if not verify_credentials(payload.username, payload.password):
        _register_failed_attempt(request)
        logger.warning("Failed ministerial login for username=%r from %s", payload.username, _client_key(request))
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "code": "invalid_credentials", "detail": "Incorrect username or password."},
        )
    _clear_failures(request)
    return {"status": "success", **issue_access_token(CONFIG.admin_username)}


@auth_router.get("/me")
def whoami(request: Request, admin: dict = Depends(get_current_admin)):
    """Validate the session and echo back its scope + expiry."""
    return {
        "status": "success",
        "username": admin["username"],
        "role": "admin",
        "expires_at": admin["exp"],
    }
