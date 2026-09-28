"""Database-backed account and JWT authentication."""

import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fast_apis import database

PBKDF2_ROUNDS = 240_000
JWT_SECRET_FILE = database.PROJECT_ROOT / "data" / ".jwt_secret"
bearer = HTTPBearer(auto_error=False)


def _secret():
    configured = os.environ.get("DINEIQ_JWT_SECRET")
    if configured:
        return configured
    JWT_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not JWT_SECRET_FILE.exists():
        JWT_SECRET_FILE.write_text(secrets.token_urlsafe(48), encoding="ascii")
    return JWT_SECRET_FILE.read_text(encoding="ascii").strip()


def _profile(db, user):
    roles = [r[0] for r in db.execute("SELECT role_name FROM user_roles WHERE user_id=?", (user["id"],))]
    locations = [r[0] for r in db.execute("SELECT location_id FROM user_locations WHERE user_id=?", (user["id"],))]
    return {"id": user["id"], "username": user["username"], "email": user["email"],
            "roles": roles, "location_ids": locations, "is_active": bool(user["is_active"])}


def register(username, email, password, role="ANALYST", location_ids=None):
    username, email = username.strip(), email.strip().lower()
    if not 2 <= len(username) <= 80 or "@" not in email or len(email) > 254:
        return None, "Enter a valid username and email."
    if not 8 <= len(password) <= 128:
        return None, "Password must be between 8 and 128 characters."
    if role not in database.ROLES:
        return None, "Invalid role."
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    try:
        with database.connection() as db:
            cursor = db.execute("INSERT INTO users(username,email,password_hash,password_salt,created_at) VALUES(?,?,?,?,?)",
                                (username, email, digest.hex(), salt.hex(), int(time.time())))
            user_id = cursor.lastrowid
            db.execute("INSERT OR IGNORE INTO user_roles(user_id,role_name) VALUES(?,?)", (user_id, role))
            for location_id in location_ids or []:
                db.execute("INSERT INTO user_locations(user_id,location_id) VALUES(?,?)", (user_id, location_id))
            profile = _profile(db, db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        database.audit("user_created", user_id, "user", user_id, {"role": role})
        return profile, None
    except Exception as exc:
        if "UNIQUE constraint failed: users.email" in str(exc):
            return None, "An account with this email already exists."
        raise


def login(email, password):
    with database.connection() as db:
        user = db.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", (email.strip(),)).fetchone()
        if not user or not user["is_active"]:
            return None
        expected = bytes.fromhex(user["password_hash"])
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(user["password_salt"]), PBKDF2_ROUNDS)
        if not hmac.compare_digest(actual, expected):
            return None
        profile = _profile(db, user)
    now = int(time.time())
    token = jwt.encode({"sub": str(profile["id"]), "iat": now, "exp": now + 3600,
                        "jti": secrets.token_hex(12)}, _secret(), algorithm="HS256")
    database.audit("login", profile["id"], "user", profile["id"])
    return {"token": token, "access_token": token, "token_type": "bearer", "expires_at": now + 3600,
            "user": profile}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required")
    try:
        claims = jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired token") from None
    with database.connection() as db:
        if db.execute("SELECT 1 FROM revoked_tokens WHERE jti=?", (claims.get("jti"),)).fetchone():
            raise HTTPException(401, "Token has been revoked")
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or not user["is_active"]:
            raise HTTPException(401, "Account unavailable")
        return _profile(db, user)


def logout(token, user):
    claims = jwt.decode(token, _secret(), algorithms=["HS256"])
    with database.connection() as db:
        db.execute("INSERT OR IGNORE INTO revoked_tokens(jti,expires_at) VALUES(?,?)",
                   (claims["jti"], claims["exp"]))
        db.execute("DELETE FROM revoked_tokens WHERE expires_at<?", (int(time.time()),))
    database.audit("logout", user["id"], "user", user["id"])


def require_roles(*allowed):
    def dependency(user=Depends(current_user)):
        if not set(user["roles"]).intersection(allowed):
            raise HTTPException(403, "Insufficient role")
        return user
    return dependency


def allowed_location(user, requested=None):
    if "REGIONAL_MANAGER" not in user["roles"] or "ADMIN" in user["roles"]:
        return requested
    locations = user["location_ids"]
    if requested is not None and requested not in locations:
        raise HTTPException(403, "Location is outside your assignment")
    if not locations:
        raise HTTPException(403, "No location assigned")
    return requested or locations
