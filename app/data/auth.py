"""Session authentication and Codeforces handle ownership verification."""
import os
import hashlib
import hmac
import secrets
from typing import Tuple
from app.data.db import get_db_connection, DEFAULT_DB_PATH

AUTH_MODE = os.getenv("AUTH_MODE", "optional").lower()
GLOBAL_PASSKEY = os.getenv("APP_PASSKEY", "")

def init_auth_table(db_path: str = DEFAULT_DB_PATH) -> None:
    """Idempotently create user_auth table."""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_auth (
                handle TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                hashed_passkey TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

def _hash_passkey(passkey: str, salt: bytes | None = None) -> Tuple[str, str]:
    """Generate PBKDF2 HMAC SHA-256 hash with cryptographic salt."""
    salt_bytes = salt or secrets.token_bytes(16)
    key_hash = hashlib.pbkdf2_hmac("sha256", passkey.encode("utf-8"), salt_bytes, 100000)
    return salt_bytes.hex(), key_hash.hex()

def verify_or_register_handle(handle: str, passkey: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[bool, str]:
    """Verify handle credentials or register initial passkey on first use.
    
    Returns:
        tuple[bool, str]: (authenticated, status_message)
    """
    clean_handle = handle.lower().strip()
    if not clean_handle:
        return False, "Handle cannot be empty."

    # Global passkey bypass if configured
    if GLOBAL_PASSKEY and passkey == GLOBAL_PASSKEY:
        return True, "Global admin passkey accepted."

    if not passkey:
        return False, "Passkey required."

    init_auth_table(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT salt, hashed_passkey FROM user_auth WHERE handle = ?;", (clean_handle,))
        row = cursor.fetchone()

        if row is None:
            # Register passkey for this handle
            salt_hex, hash_hex = _hash_passkey(passkey)
            conn.execute(
                "INSERT INTO user_auth (handle, salt, hashed_passkey) VALUES (?, ?, ?);",
                (clean_handle, salt_hex, hash_hex)
            )
            return True, f"Handle '{clean_handle}' claimed and passkey registered."

        # Existing user: verify passkey
        salt_bytes = bytes.fromhex(row["salt"])
        _, check_hash = _hash_passkey(passkey, salt=salt_bytes)

        if hmac.compare_digest(check_hash, row["hashed_passkey"]):
            return True, "Authentication successful."
        else:
            return False, "Incorrect passkey for this handle."

def is_auth_required() -> bool:
    """Return whether authentication is strictly enforced in current environment."""
    return AUTH_MODE in ("required", "true", "1") or bool(GLOBAL_PASSKEY)
