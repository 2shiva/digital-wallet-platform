
from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return a secure hash of a plain-text password."""
    if not password:
        raise ValueError("Password cannot be empty")

    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a plain-text password against its stored hash."""
    if not plain_password or not hashed_password:
        return False

    return password_hash.verify(plain_password, hashed_password)
