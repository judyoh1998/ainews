from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import get_db

_bearer = HTTPBearer(auto_error=False)


# ── Password hashing (stdlib-only) ──


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── Simple HMAC token (stdlib-only, no PyJWT dependency) ──


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = json.dumps({"sub": str(user_id), "exp": int(exp.timestamp())})
    payload_b64 = _b64url_encode(payload.encode())
    sig = hmac.new(
        settings.jwt_secret.encode(), payload_b64.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def decode_token(token: str) -> Optional[int]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        # Verify signature
        expected_sig = hmac.new(
            settings.jwt_secret.encode(), payload_b64.encode(), hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        # Decode payload
        payload = json.loads(_b64url_decode(payload_b64))
        # Check expiry
        if datetime.now(timezone.utc).timestamp() > payload.get("exp", 0):
            return None
        return int(payload["sub"])
    except Exception:
        return None


# ── User CRUD ──


def create_user(
    db: sqlite3.Connection, username: str, email: str, password: str
) -> dict:
    pw_hash = _hash_password(password)
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email.lower(), pw_hash),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        msg = str(exc).lower()
        if "email" in msg:
            raise HTTPException(409, "Email already registered")
        if "username" in msg:
            raise HTTPException(409, "Username already taken")
        raise HTTPException(409, "User already exists")
    return {"id": cur.lastrowid, "username": username, "email": email.lower()}


def authenticate_user(
    db: sqlite3.Connection, email: str, password: str
) -> Optional[dict]:
    row = db.execute(
        "SELECT id, username, email, password_hash FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "email": row["email"]}


# ── FastAPI dependency: get current user ──


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    if creds is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing authorization header"
        )
    user_id = decode_token(creds.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    row = db.execute(
        "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return {"id": row["id"], "username": row["username"], "email": row["email"]}
