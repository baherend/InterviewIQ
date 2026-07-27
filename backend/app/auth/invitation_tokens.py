import hashlib
import secrets

# 32 random bytes (256 bits) URL-safe encoded — cryptographically secure
# (secrets.token_urlsafe uses os.urandom under the hood), not guessable,
# and short enough to sit comfortably in a query string.
_TOKEN_BYTES = 32


def generate_invitation_token() -> str:
    """Returns a new raw, cryptographically secure invitation token.

    The raw value is returned to the caller (creation/resend response, or
    a locally displayed acceptance URL) exactly once and is never stored —
    only `hash_invitation_token(...)` of it is persisted. Treat the return
    value as a secret: never log it.
    """
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_invitation_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw invitation token, for storage/lookup.

    Invitation tokens are single-use, server-generated, high-entropy
    random values (not user-chosen secrets reused elsewhere), so a fast
    cryptographic hash is the appropriate and standard choice here — unlike
    passwords, there is no offline-guessing risk to mitigate with a slow
    hash (the token space is 2^256; brute force is infeasible regardless
    of hash speed). Lookup is a plain indexed/unique equality match against
    this hash: an attacker who does not already hold the raw token cannot
    produce a colliding hash, so no extra constant-time comparison is
    needed beyond the database's own equality check.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
