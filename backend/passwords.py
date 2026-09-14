"""Argon2id password handling; no plaintext passwords are persisted."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

hasher = PasswordHasher()

def hash_password(password):
    return hasher.hash(password)

def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (InvalidHashError, VerificationError):
        return False

# Explicit homologation identities; resets keep their established Demo flow.
DEMO_EMAILS = frozenset({
    'demo@tagcheck.local', 'supervisor@tagcheck.local',
    'operator@tagcheck.local', 'viewer@tagcheck.local',
})

def is_demo_account(user):
    return user.email.strip().lower() in DEMO_EMAILS
