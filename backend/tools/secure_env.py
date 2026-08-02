"""Manages StockFlow's Windows DPAPI-encrypted local environment file."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config.secure_env import (  # noqa: E402
    PLAIN_ENV_FILENAME,
    SECURE_ENV_FILENAME,
    decrypt_environment_file,
    parse_environment_text,
    write_encrypted_environment,
)

PLAIN_ENV_PATH = BACKEND_DIR / PLAIN_ENV_FILENAME
SECURE_ENV_PATH = BACKEND_DIR / SECURE_ENV_FILENAME
VALID_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def require_windows():
    """Stops local encrypted-environment commands outside Windows."""

    if os.name != "nt":
        print("ERROR: This command requires Windows DPAPI.")
        sys.exit(1)


def serialize_value(value):
    """Quotes values safely for python-dotenv parsing."""

    if re.fullmatch(r"[A-Za-z0-9_./:+-]+", value):
        return value

    return json.dumps(value)


def upsert_environment_value(plain_text, key, value):
    """Adds or replaces one key without exposing other values."""

    replacement = f"{key}={serialize_value(value)}"
    pattern = re.compile(
        rf"^\s*{re.escape(key)}\s*=",
    )
    lines = plain_text.splitlines()
    updated_lines = []
    replaced = False

    for line in lines:
        if pattern.match(line) and not replaced:
            updated_lines.append(replacement)
            replaced = True
        elif pattern.match(line):
            # Removes duplicate definitions for the same secret.
            continue
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(replacement)

    return "\n".join(updated_lines).rstrip() + "\n"


def verify_encrypted_value(expected_text):
    """Confirms the newly written encrypted file decrypts exactly."""

    decrypted_text = decrypt_environment_file(SECURE_ENV_PATH)

    if decrypted_text != expected_text:
        print("ERROR: Encrypted environment verification failed.")
        sys.exit(1)


def migrate_plain_environment():
    """Encrypts .env, verifies it, then removes plaintext local copies."""

    require_windows()

    if not PLAIN_ENV_PATH.exists():
        print("ERROR: backend\\.env was not found.")
        sys.exit(1)

    if SECURE_ENV_PATH.exists():
        print("ERROR: backend\\.env.enc already exists.")
        print("Use the set or status command instead of migrating again.")
        sys.exit(1)

    plain_text = PLAIN_ENV_PATH.read_text(encoding="utf-8")

    if not plain_text.strip():
        print("ERROR: backend\\.env is empty.")
        sys.exit(1)

    write_encrypted_environment(
        SECURE_ENV_PATH,
        plain_text,
    )
    verify_encrypted_value(plain_text)

    PLAIN_ENV_PATH.unlink()

    removed_backups = []
    backup_patterns = (
        ".env.before-*.auto.txt",
        ".env.backup.txt",
        ".env.*.backup.txt",
    )

    for pattern in backup_patterns:
        for backup_path in BACKEND_DIR.glob(pattern):
            backup_path.unlink()
            removed_backups.append(backup_path.name)

    print("CREATED: backend\\.env.enc")
    print("VERIFIED: Encrypted values decrypt correctly for this Windows user.")
    print("REMOVED: backend\\.env")

    for backup_name in removed_backups:
        print(f"REMOVED: backend\\{backup_name}")

    print(
        "IMPORTANT: The encrypted file is tied to this Windows user and computer."
    )
    print(
        "IMPORTANT: OneDrive history or deleted-file recovery may still contain "
        "older plaintext copies."
    )
    print(
        "SUCCESS: StockFlow now uses an encrypted local environment file."
    )


def set_encrypted_value(key):
    """Prompts without echo and updates one encrypted value."""

    require_windows()

    if not VALID_KEY_PATTERN.fullmatch(key):
        print(
            "ERROR: Use an uppercase environment key such as "
            "PAYMENT_GATEWAY_SECRET_KEY."
        )
        sys.exit(1)

    if not SECURE_ENV_PATH.exists():
        print("ERROR: backend\\.env.enc does not exist. Run migrate first.")
        sys.exit(1)

    first_value = getpass.getpass(f"Enter {key}: ")
    second_value = getpass.getpass(f"Confirm {key}: ")

    if not first_value:
        print("ERROR: The value cannot be empty.")
        sys.exit(1)

    if first_value != second_value:
        print("ERROR: The two values did not match.")
        sys.exit(1)

    if "\n" in first_value or "\r" in first_value:
        print("ERROR: Environment values cannot contain new lines.")
        sys.exit(1)

    plain_text = decrypt_environment_file(SECURE_ENV_PATH)
    next_text = upsert_environment_value(
        plain_text,
        key,
        first_value,
    )
    write_encrypted_environment(
        SECURE_ENV_PATH,
        next_text,
    )
    verify_encrypted_value(next_text)

    print(f"UPDATED: {key} (value hidden)")
    print("SUCCESS: The encrypted environment file was verified.")


def rotate_django_secret():
    """Generates a new Django signing key directly inside the encrypted file."""

    require_windows()

    if not SECURE_ENV_PATH.exists():
        print("ERROR: backend\\.env.enc does not exist. Run migrate first.")
        sys.exit(1)

    plain_text = decrypt_environment_file(SECURE_ENV_PATH)
    next_text = upsert_environment_value(
        plain_text,
        "DJANGO_SECRET_KEY",
        secrets.token_urlsafe(64),
    )
    write_encrypted_environment(
        SECURE_ENV_PATH,
        next_text,
    )
    verify_encrypted_value(next_text)

    print("UPDATED: DJANGO_SECRET_KEY (new value hidden)")
    print("SUCCESS: The encrypted environment file was verified.")


def show_status():
    """Lists configured keys without printing any values."""

    require_windows()

    if not SECURE_ENV_PATH.exists():
        print("ENCRYPTED_ENV: MISSING")
        sys.exit(1)

    values = parse_environment_text(
        decrypt_environment_file(SECURE_ENV_PATH),
    )

    print("ENCRYPTED_ENV: READY")

    for key in sorted(values):
        state = "SET" if str(values[key]).strip() else "EMPTY"
        print(f"{key}: {state}")


def build_parser():
    """Builds the local secure-environment command interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Manage StockFlow local secrets with Windows DPAPI."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "migrate",
        help="Encrypt backend\\.env and remove plaintext copies.",
    )
    subparsers.add_parser(
        "status",
        help="Show configured key names without values.",
    )

    set_parser = subparsers.add_parser(
        "set",
        help="Set one encrypted environment value using a hidden prompt.",
    )
    set_parser.add_argument("key")

    subparsers.add_parser(
        "rotate-django-key",
        help="Generate a new encrypted DJANGO_SECRET_KEY.",
    )

    return parser


def main():
    """Runs the selected secure-environment operation."""

    arguments = build_parser().parse_args()

    if arguments.command == "migrate":
        migrate_plain_environment()
    elif arguments.command == "status":
        show_status()
    elif arguments.command == "set":
        set_encrypted_value(arguments.key)
    elif arguments.command == "rotate-django-key":
        rotate_django_secret()


if __name__ == "__main__":
    main()
