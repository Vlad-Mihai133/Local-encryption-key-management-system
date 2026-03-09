from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """CLI placeholder (Sprint 1).

    Next sprint expectations:
    - Add subcommands:
      - keygen (AES/RSA)
      - encrypt (file -> encrypted artifact)
      - decrypt (encrypted artifact -> decrypted)
      - list-keys / list-files / list-operations

    - Wire up DB session:
      - Read DATABASE_URL from env
      - Open SQLAlchemy Session

    - Wire up service layer:
      - Instantiate CryptoService
      - Call service methods

    - Decide output format:
      - human-readable text vs JSON
    """

    parser = argparse.ArgumentParser(prog="klm", description="Local key management system")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="Generate a key and store it encrypted in DB")
    keygen.add_argument("--name", required=True)
    keygen.add_argument("--algorithm", required=True, help="e.g. AES, RSA")
    keygen.add_argument("--key-type", required=True, help="symmetric | asymmetric_private | asymmetric_public")
    keygen.add_argument("--usage", required=True, help="file_encryption | key_wrapping | signing")

    enc = sub.add_parser("encrypt", help="Encrypt a file")
    enc.add_argument("--file", required=True)
    enc.add_argument("--key-id", required=True)
    enc.add_argument("--variant", required=True, help="algorithm variant name")

    dec = sub.add_parser("decrypt", help="Decrypt an artifact")
    dec.add_argument("--artifact-id", required=True)
    dec.add_argument("--key-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # TODO (next sprint):
    # - Create engine/session from DATABASE_URL
    # - Instantiate CryptoService
    # - Dispatch based on args.command

    raise NotImplementedError(f"Command '{args.command}' is not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
