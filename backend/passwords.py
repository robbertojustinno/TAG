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
