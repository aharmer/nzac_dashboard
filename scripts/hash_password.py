"""Generate a bcrypt hash for a Names-database editor password.

Run this locally, choose a password when prompted, and paste the resulting hash
into .streamlit/secrets.toml (or Streamlit Community Cloud's secrets manager) --
never the plaintext password itself.

    python scripts/hash_password.py

Note: this uses a plain, visible input() rather than getpass() -- getpass's
hidden-input mode doesn't accept a clipboard paste in some Windows terminals
(e.g. Git Bash/MinTTY), silently inserting the raw Ctrl+V byte instead of the
pasted text. Visible input is the price of a paste that actually works; run
this somewhere private.
"""

import streamlit_authenticator as stauth

if __name__ == "__main__":
    password = input("Password to hash (visible as you type/paste): ")
    confirm = input("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    print("\nHashed password (paste this into secrets.toml):\n")
    print(stauth.Hasher.hash(password))
