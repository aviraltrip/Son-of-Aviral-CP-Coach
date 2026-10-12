"""Session authentication and Codeforces handle ownership verification."""
import os
import hashlib
import hmac
import secrets
from app.data.db import get_user_auth, save_user_auth, ensure_db_initialized, DEFAULT_DB_PATH

AUTH_MODE = os.getenv("AUTH_MODE", "optional").lower()
GLOBAL_PASSKEY = os.getenv("APP_PASSKEY", "")

def init_auth_table(db_path: str = DEFAULT_DB_PATH) -> None:
    """Ensure database tables including user_auth are initialized."""
    ensure_db_initialized(db_path)

def _hash_passkey(passkey: str, salt: bytes | None = None) -> tuple[str, str]:
    """Generate PBKDF2 HMAC SHA-256 hash with cryptographic salt."""
    salt_bytes = salt or secrets.token_bytes(16)
    key_hash = hashlib.pbkdf2_hmac("sha256", passkey.encode("utf-8"), salt_bytes, 100000)
    return salt_bytes.hex(), key_hash.hex()

def verify_or_register_handle(handle: str, passkey: str, db_path: str = DEFAULT_DB_PATH) -> tuple[bool, str]:
    """Verify handle credentials or register initial passkey on first use.
    
    Returns:
        tuple[bool, str]: (authenticated, status_message)
    """
    clean_handle = handle.lower().strip()
    if not clean_handle:
        return False, "Handle cannot be empty."

    if GLOBAL_PASSKEY and passkey == GLOBAL_PASSKEY:
        return True, "Global admin passkey accepted."

    if not passkey:
        return False, "Passkey required."

    ensure_db_initialized(db_path)
    row = get_user_auth(clean_handle, db_path=db_path)

    if row is None:
        salt_hex, hash_hex = _hash_passkey(passkey)
        save_user_auth(clean_handle, salt_hex, hash_hex, db_path=db_path)
        return True, f"Handle '{clean_handle}' claimed and passkey registered."

    salt_bytes = bytes.fromhex(row["salt"])
    _, check_hash = _hash_passkey(passkey, salt=salt_bytes)

    if hmac.compare_digest(check_hash, row["hashed_passkey"]):
        return True, "Authentication successful."
    else:
        return False, "Incorrect passkey for this handle."

def is_auth_required() -> bool:
    """Return whether authentication is strictly enforced in current environment."""
    return AUTH_MODE in ("required", "true", "1") or bool(GLOBAL_PASSKEY)
