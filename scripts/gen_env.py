"""Create .env from .env.example with fresh secrets and an RS256 key pair.

Usage:
    pip install cryptography
    python scripts/gen_env.py           # refuses to overwrite an existing .env
    python scripts/gen_env.py --force   # overwrite (then also reset the postgres volume)
"""

import base64
import secrets
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    sys.exit("Missing dependency: run  pip install cryptography  and try again.")

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def main() -> None:
    if TARGET.exists() and "--force" not in sys.argv:
        sys.exit(".env already exists. Use --force to overwrite it.")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    values = {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(40),
        "SERVICE_TOKEN": secrets.token_urlsafe(32),
        "JWT_PRIVATE_KEY_B64": b64(private_pem),
        "JWT_PUBLIC_KEY_B64": b64(public_pem),
    }

    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        name = line.split("=", 1)[0].strip()
        if not line.startswith("#") and "=" in line and name in values:
            line = f"{name}={values[name]}"
        lines.append(line)

    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
