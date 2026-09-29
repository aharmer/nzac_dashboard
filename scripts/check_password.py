"""Diagnostic: check a password against the hash stored in secrets.toml directly,
bypassing Streamlit and streamlit-authenticator entirely.

    python scripts/check_password.py <username>
"""

import sys
import tomllib
from pathlib import Path

import bcrypt

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/check_password.py <username>")
    username = sys.argv[1]

    secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)

    entry = secrets.get("auth", {}).get("usernames", {}).get(username)
    if entry is None:
        raise SystemExit(f"No [auth.usernames.{username}] entry found in secrets.toml")

    stored_hash = entry["password"]
    print(f"Stored hash for '{username}': {stored_hash}")
    print(f"Hash length: {len(stored_hash)} (should be 60)")

    password = input("Password to check (visible as you type/paste): ")
    print(f"Typed/pasted password length: {len(password)} characters")
    print(f"Repr (shows hidden whitespace/unicode): {password!r}")

    result = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    print(f"\nMATCH: {result}")
