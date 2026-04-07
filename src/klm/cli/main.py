from __future__ import annotations

import argparse
import uuid

from klm.db.session import create_db_engine, create_session_factory
from klm.services.crypto_service import CryptoService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klm", description="Local key management system")
    sub = parser.add_subparsers(dest="command")

    artifact_add = sub.add_parser("artifact-add", help="Add new artifact")
    artifact_add.add_argument("--file-id", required=True)
    artifact_add.add_argument("--artifact-type-id", required=True)
    artifact_add.add_argument("--path", required=True)
    artifact_add.add_argument("--size-bytes", required=True, type=int)
    artifact_add.add_argument("--hash", required=True)

    artifact_get = sub.add_parser("artifact-get", help="Get artifact by id")
    artifact_get.add_argument("--artifact-id", required=True)

    artifact_list = sub.add_parser("artifact-list", help="List all artifacts")

    artifact_delete = sub.add_parser("artifact-delete", help="Delete artifact by id")
    artifact_delete.add_argument("--artifact-id", required=True)

    keygen = sub.add_parser("keygen", help="Generate a key and store it encrypted in DB")
    keygen.add_argument("--name", required=True)
    keygen.add_argument("--algorithm", required=True, help="Algorithm name (e.g. AES, RSA)")
    keygen.add_argument("--variant", required=False, help="Algorithm variant name (optional, will prompt if not provided)")
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

    artifact_update = sub.add_parser("artifact-update", help="Update artifact path")
    artifact_update.add_argument("--artifact-id", required=True)
    artifact_update.add_argument("--new-path", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    engine = create_db_engine()
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        service = CryptoService(session=session)

        try:
            if args.command == "artifact-add":
                from klm.db.repositories import FileArtifactRepository
                repo = FileArtifactRepository(session)
                from klm.db import models
                artifact = models.FileArtifact(
                    file_id=uuid.UUID(args.file_id),
                    artifact_type_id=uuid.UUID(args.artifact_type_id),
                    path=args.path,
                    size_bytes=args.size_bytes,
                    hash=args.hash
                )
                repo.add(artifact)
                session.commit()
                print(f"Artifact added: {artifact.id}")
                return 0

            if args.command == "artifact-get":
                from klm.db.repositories import FileArtifactRepository
                repo = FileArtifactRepository(session)
                artifact = repo.get(uuid.UUID(args.artifact_id))
                if not artifact:
                    print("Artifact not found.")
                    return 2
                print(f"Artifact: {artifact}")
                return 0

            if args.command == "artifact-list":
                from klm.db.repositories import FileArtifactRepository
                repo = FileArtifactRepository(session)
                artifacts = repo.list_all()
                for artifact in artifacts:
                    print(f"- {artifact}")
                return 0

            if args.command == "artifact-delete":
                from klm.db.repositories import FileArtifactRepository
                repo = FileArtifactRepository(session)
                artifact = repo.get(uuid.UUID(args.artifact_id))
                if not artifact:
                    print("Artifact not found.")
                    return 2
                repo.delete(artifact)
                session.commit()
                print("Artifact deleted.")
                return 0

            if args.command == "artifact-update":
                from klm.db.repositories import FileArtifactRepository
                repo = FileArtifactRepository(session)
                artifact = repo.get(uuid.UUID(args.artifact_id))
                if not artifact:
                    print("Artifact not found.")
                    return 2
                repo.update_path(artifact, args.new_path)
                print("Path updated.")
                return 0

            if args.command == "keygen":
                from klm.db.repositories import AlgorithmRepository, AlgorithmVariantRepository
                alg_repo = AlgorithmRepository(session)
                variant_repo = AlgorithmVariantRepository(session)
                alg = alg_repo.get_by_name(args.algorithm)
                if not alg:
                    print(f"Algorithm '{args.algorithm}' not found.")
                    return 2
                variants = variant_repo.list_all()
                alg_variants = [v for v in variants if v.algorithm_id == alg.id]
                variant_name = args.variant
                if not variant_name:
                    print("Available variants:")
                    for v in alg_variants:
                        print(f"- {v.name}")
                    variant_name = input("Select variant: ")
                variant = next((v for v in alg_variants if v.name == variant_name), None)
                if not variant:
                    print(f"Variant '{variant_name}' not found for algorithm '{args.algorithm}'.")
                    return 2
                key_id = service.keygen(
                    algorithm=args.algorithm,
                    key_type=args.key_type,
                    usage=args.usage,
                    name=args.name,
                    params={"variant_id": str(variant.id)},
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