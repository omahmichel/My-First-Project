"""Loads StockFlow local secrets from a Windows DPAPI-encrypted file."""

from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes
from io import StringIO
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values, load_dotenv

SECURE_ENV_FILENAME = ".env.enc"
PLAIN_ENV_FILENAME = ".env"
SECURE_ENV_HEADER = b"STOCKFLOW-DPAPI-V1\n"
DPAPI_ENTROPY = b"StockFlow local environment v1"
CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DataBlob(ctypes.Structure):
    """Represents the Windows DATA_BLOB structure used by DPAPI."""

    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _require_windows():
    """Stops DPAPI operations on unsupported operating systems."""

    if os.name != "nt":
        raise ImproperlyConfigured(
            "StockFlow encrypted local environment files require Windows DPAPI."
        )


def _get_windows_apis():
    """Loads typed Windows DPAPI functions without pointer truncation."""

    _require_windows()

    crypt32 = ctypes.WinDLL(
        "crypt32",
        use_last_error=True,
    )
    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    return crypt32, kernel32


def _build_blob(value):
    """Creates a DATA_BLOB while retaining its backing memory buffer."""

    if not value:
        return DataBlob(0, None), None

    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    blob = DataBlob(
        len(value),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _copy_and_release_blob(blob, kernel32):
    """Copies DPAPI output into Python memory and releases Windows memory."""

    if not blob.pbData or not blob.cbData:
        return b""

    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        kernel32.LocalFree(
            ctypes.cast(blob.pbData, wintypes.HLOCAL),
        )


def protect_bytes(value):
    """Encrypts bytes for the current Windows user with DPAPI."""

    crypt32, kernel32 = _get_windows_apis()
    input_blob, input_buffer = _build_blob(value)
    entropy_blob, entropy_buffer = _build_blob(DPAPI_ENTROPY)
    output_blob = DataBlob()

    result = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "StockFlow local environment",
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )

    # Keeps backing buffers alive until the Windows API call completes.
    _ = input_buffer, entropy_buffer

    if not result:
        raise ctypes.WinError(ctypes.get_last_error())

    return _copy_and_release_blob(output_blob, kernel32)


def unprotect_bytes(value):
    """Decrypts bytes for the current Windows user with DPAPI."""

    crypt32, kernel32 = _get_windows_apis()
    input_blob, input_buffer = _build_blob(value)
    entropy_blob, entropy_buffer = _build_blob(DPAPI_ENTROPY)
    output_blob = DataBlob()

    result = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )

    # Keeps backing buffers alive until the Windows API call completes.
    _ = input_buffer, entropy_buffer

    if not result:
        raise ctypes.WinError(ctypes.get_last_error())

    return _copy_and_release_blob(output_blob, kernel32)


def encrypt_environment_text(plain_text):
    """Builds the versioned encrypted file payload."""

    encrypted_value = protect_bytes(plain_text.encode("utf-8"))
    encoded_value = base64.b64encode(encrypted_value)
    return SECURE_ENV_HEADER + encoded_value + b"\n"


def decrypt_environment_payload(payload):
    """Validates and decrypts one StockFlow encrypted environment payload."""

    if not payload.startswith(SECURE_ENV_HEADER):
        raise ImproperlyConfigured(
            "The StockFlow encrypted environment file has an invalid format."
        )

    encoded_value = payload[len(SECURE_ENV_HEADER) :].strip()

    try:
        encrypted_value = base64.b64decode(
            encoded_value,
            validate=True,
        )
        return unprotect_bytes(encrypted_value).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ImproperlyConfigured(
            "The StockFlow encrypted environment file is corrupted."
        ) from exc
    except OSError as exc:
        raise ImproperlyConfigured(
            "The StockFlow encrypted environment file could not be decrypted "
            "by this Windows account."
        ) from exc


def decrypt_environment_file(path):
    """Reads and decrypts one local encrypted environment file."""

    return decrypt_environment_payload(Path(path).read_bytes())


def write_encrypted_environment(path, plain_text):
    """Writes an encrypted environment file atomically."""

    destination = Path(path)
    temporary_path = destination.with_name(
        f"{destination.name}.tmp",
    )
    temporary_path.write_bytes(
        encrypt_environment_text(plain_text),
    )
    os.replace(temporary_path, destination)


def parse_environment_text(plain_text):
    """Parses dotenv text without writing decrypted values to disk."""

    values = dotenv_values(stream=StringIO(plain_text))

    return {
        key: value
        for key, value in values.items()
        if key and value is not None
    }


def load_backend_environment(base_dir):
    """Loads encrypted local values or normal deployment environment values."""

    base_path = Path(base_dir)
    encrypted_path = base_path / SECURE_ENV_FILENAME
    plain_path = base_path / PLAIN_ENV_FILENAME

    if encrypted_path.exists():
        plain_text = decrypt_environment_file(encrypted_path)
        values = parse_environment_text(plain_text)

        # Existing hosting variables take precedence over local encrypted values.
        for key, value in values.items():
            os.environ.setdefault(key, value)

        return "encrypted"

    if plain_path.exists():
        # Temporary migration fallback until the local file is encrypted.
        load_dotenv(plain_path, override=False)
        return "plaintext"

    # Production hosts supply values through their protected environment store.
    return "environment"
