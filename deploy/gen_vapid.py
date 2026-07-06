#!/usr/bin/env python3
"""Erzeugt ein VAPID-Schluesselpaar fuer Web-Push.

  python3 deploy/gen_vapid.py <pfad-fuer-private.pem>

Schreibt den privaten Schluessel als PEM (chmod 600) an den angegebenen Pfad
und gibt den oeffentlichen Application-Server-Key (base64url) auf stdout aus —
diesen in die .env als VAPID_PUBLIC_KEY eintragen, den PEM-Pfad als
VAPID_PRIVATE_KEY.
"""
import base64
import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main():
    if len(sys.argv) < 2:
        print("Usage: gen_vapid.py <private_key.pem>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]

    priv = ec.generate_private_key(ec.SECP256R1())
    pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with open(path, "wb") as f:
        f.write(pem)
    os.chmod(path, 0o600)

    raw_pub = priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    app_key = base64.urlsafe_b64encode(raw_pub).rstrip(b"=").decode()

    print("VAPID_PUBLIC_KEY=" + app_key)
    print("PRIVATE_PEM_PATH=" + os.path.abspath(path), file=sys.stderr)


if __name__ == "__main__":
    main()
