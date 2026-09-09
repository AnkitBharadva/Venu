"""Security and Cryptography Module for Air-Gapped Content Transformation.

Implements:
- AES-256-GCM authenticated encryption at rest for uploaded source files and outputs.
- SHA-256 checksum computation for integrity and tamper-evidence.
- Key management strictly loaded from environment configuration (never hardcoded).
"""

import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def get_encryption_key() -> bytes:
    """Retrieve and validate the 256-bit (32-byte) AES key from environment settings."""
    settings = get_settings()
    raw_key = settings.STORAGE_ENCRYPTION_KEY.strip()

    # Try hex decoding if 64 hex characters
    if len(raw_key) == 64:
        try:
            key_bytes = bytes.fromhex(raw_key)
            if len(key_bytes) == 32:
                return key_bytes
        except ValueError:
            pass

    # If raw string is exactly 32 bytes
    encoded = raw_key.encode("utf-8")
    if len(encoded) == 32:
        return encoded

    # Deterministic SHA-256 derivation if passphrase is provided
    return hashlib.sha256(encoded).digest()


def compute_sha256(data: bytes) -> str:
    """Compute standard SHA-256 hex digest of raw binary data."""
    return hashlib.sha256(data).hexdigest()


def encrypt_bytes(raw_data: bytes, associated_data: bytes | None = None) -> bytes:
    """Encrypt byte payload using AES-256-GCM with a fresh 12-byte nonce.

    Format of returned payload:
    [12-byte nonce] + [ciphertext + 16-byte authentication tag]
    """
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce as recommended for GCM
    ciphertext = aesgcm.encrypt(nonce, raw_data, associated_data)
    return nonce + ciphertext


def decrypt_bytes(encrypted_payload: bytes, associated_data: bytes | None = None) -> bytes:
    """Decrypt an AES-256-GCM payload.

    Raises:
        ValueError: If payload is too short to contain a valid nonce.
        InvalidTag: If the ciphertext was tampered with or key is incorrect.
    """
    if len(encrypted_payload) < 28:  # 12-byte nonce + 16-byte tag minimum
        raise ValueError("Encrypted payload is corrupted or truncated (insufficient length).")

    key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = encrypted_payload[:12]
    ciphertext_and_tag = encrypted_payload[12:]
    return aesgcm.decrypt(nonce, ciphertext_and_tag, associated_data)


def save_encrypted_file(raw_data: bytes, target_path: Path | str) -> str:
    """Encrypt raw data and save it directly to the designated disk path.

    Returns the string representation of the written file path.
    """
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = encrypt_bytes(raw_data)
    path.write_bytes(encrypted)
    return str(path.resolve())


def read_decrypted_file(source_path: Path | str) -> bytes:
    """Read an encrypted file from disk and return the decrypted original bytes."""
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Encrypted file not found at: {path}")
    encrypted = path.read_bytes()
    return decrypt_bytes(encrypted)
