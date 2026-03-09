from __future__ import annotations

import argparse
import uuid

from klm.db.session import create_db_engine, create_session_factory
from klm.services.crypto_service import CryptoService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klm", description="Local key management system")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="Generate a key and store it encrypted in DB")
    keygen.add_argument("--name", required=True)
    keygen.add_argument("--algorithm", required=True, help="e.g. AES, RSA")
    keygen.add_argument(
        "--key-type",
        required=True,
        help="symmetric | asymmetric_private | asymmetric_public",
    )
    keygen.add_argument(
        "--usage",
        required=True,
        help="file_encryption | key_wrapping | signing",
    )

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

    engine = create_db_engine()
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        service = CryptoService(session=session)

        try:
            if args.command == "keygen":
                key_id = service.keygen(
                    algorithm=args.algorithm,
                    key_type=args.key_type,
                    usage=args.usage,
                    name=args.name,
                    params={},
                )
                session.commit()
                print(f"Key created: {key_id}")
                return 0

            if args.command == "encrypt":
                artifact_id = service.encrypt_file(
                    file_path=args.file,
                    key_id=uuid.UUID(args.key_id),
                    algorithm_variant=args.variant,
                    params={},
                )
                session.commit()
                print(f"Encrypted artifact created: {artifact_id}")
                return 0

            if args.command == "decrypt":
                artifact_id = service.decrypt_file(
                    artifact_id=uuid.UUID(args.artifact_id),
                    key_id=uuid.UUID(args.key_id),
                    params={},
                )
                session.commit()
                print(f"Decrypted artifact created: {artifact_id}")
                return 0

            parser.error(f"Unknown command: {args.command}")
            return 2

        except ValueError as exc:
            session.rollback()
            print(f"Invalid input: {exc}")
            return 2

        except NotImplementedError as exc:
            session.rollback()
            print(f"Not implemented yet: {exc}")
            return 1

        except Exception as exc:
            session.rollback()
            print(f"Error: {exc}")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())