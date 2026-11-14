"""Password hashing with Argon2id.

Parameters are OWASP's recommended minimum (19 MiB, t=2, p=1): memory-hard enough to
make GPU cracking expensive, light enough that a 512 MB instance can verify several
logins at once. ``needs_rehash`` lets the parameters be raised later — old hashes are
upgraded transparently on the user's next successful login.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)

# Verified against when the email is unknown, so "no such user" costs the same time as
# "wrong password" and response timing can't be used to enumerate accounts.
_DUMMY_HASH = _hasher.hash("atlas-timing-equalizer")

MIN_LENGTH = 8
MAX_LENGTH = 128  # bounds the hashing cost an attacker can make us pay per request

# The most common passwords in breach corpora; NIST 800-63B asks to reject these.
_COMMON = frozenset({
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou", "11111111", "00000000", "abc12345",
    "letmein1", "welcome1", "admin123", "passw0rd", "baseball", "football",
    "sunshine", "princess", "trustno1", "superman", "starwars", "whatever",
})


def password_problem(password: str, email: str | None = None) -> str | None:
    """A human-readable reason the password is unacceptable, or ``None``."""
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Password must be at most {MAX_LENGTH} characters."
    lowered = password.lower()
    if lowered in _COMMON or len(set(password)) < 4:
        return "That password is too common. Please choose another."
    if email and lowered == email.lower():
        return "Password must not be your email address."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Constant-shape check: always runs one Argon2 verification."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True
