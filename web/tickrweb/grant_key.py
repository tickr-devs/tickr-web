"""The RSA key that signs bot grants: made once on the server, never leaves it.

`python -m tickrweb.grant_key PATH` writes a new key to PATH (mode 600) only if PATH does not exist,
so a restart or a deploy keeps the key the bot has pinned. Prints nothing about the key.
"""

import os
import sys
import tempfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# RSA public exponent (the standard F4 value) and key size in bits (RS256, NIST minimum 2048).
PUBLIC_EXPONENT = 65537
KEY_BITS = 3072


def new_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=PUBLIC_EXPONENT, key_size=KEY_BITS)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


def ensure(path: str) -> bool:
    """Creates the key file if it is missing; returns whether it made one.

    The key is written to a temporary file in the same folder and then linked into place, so the
    key file is either complete or absent: a crash mid-write never leaves an empty key behind.
    """
    if os.path.exists(path):
        return False
    folder = os.path.dirname(os.path.abspath(path))
    handle, temporary = tempfile.mkstemp(dir=folder, prefix=".grant-key-")  # mode 600
    try:
        with os.fdopen(handle, "w", encoding="ascii") as out:
            out.write(new_private_key_pem())
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:  # another start made it first; keep that one
            return False
        return True
    finally:
        os.unlink(temporary)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m tickrweb.grant_key PATH")
    if ensure(sys.argv[1]):
        print("tickrweb: made a new grant signing key")
