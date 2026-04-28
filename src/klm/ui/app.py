from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog, ttk

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from klm.db import models
from klm.db.session import create_db_engine, create_session_factory
from klm.services.crypto_service import CryptoService


@dataclass(frozen=True)
class Choice:
    label: str
    value: object


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _unique_name(existing: set[str], base: str) -> str:
    if base not in existing:
        return base
    stem = base
    n = 2
    while f"{stem}-{n}" in existing:
        n += 1
    return f"{stem}-{n}"


def _get_or_create_by_name(session, model_cls, name: str):
    obj = session.scalar(select(model_cls).where(model_cls.name == name))
    if obj is not None:
        return obj
    obj = model_cls(name=name)
    session.add(obj)
    session.flush()
    return obj


def _load_artifact_metadata(path: Path) -> dict[str, object]:
    meta_path = Path(str(path) + ".meta")
    if not meta_path.exists():
        raise FileNotFoundError(str(meta_path))
    return json.loads(meta_path.read_text(encoding="utf-8"))


class KLMApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KLM - selectie algoritm/cheie/fisier")
        self.geometry("900x520")

        self.engine = create_db_engine()
        self.Session = create_session_factory(self.engine)

        self.algorithms: list[models.Algorithm] = []
        self.variants: list[models.AlgorithmVariant] = []
        self.keys: list[models.Key] = []
        self.files: list[models.File] = []

        self.selected_algorithm: models.Algorithm | None = None
        self.selected_variant: models.AlgorithmVariant | None = None
        self.selected_key: models.Key | None = None
        self.selected_file: models.File | None = None

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(root, text="Selectare algoritm / cheie / fisier", font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w")

        form = ttk.Frame(root)
        form.pack(fill=tk.X, pady=(12, 4))

        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Algoritm").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        self.algorithm_cb = ttk.Combobox(form, state="readonly")
        self.algorithm_cb.grid(row=0, column=1, sticky="ew", pady=6)
        self.algorithm_cb.bind("<<ComboboxSelected>>", self._on_algorithm_selected)

        ttk.Label(form, text="Varianta").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        self.variant_cb = ttk.Combobox(form, state="readonly")
        self.variant_cb.grid(row=1, column=1, sticky="ew", pady=6)
        self.variant_cb.bind("<<ComboboxSelected>>", self._on_variant_selected)

        ttk.Label(form, text="Cheie").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.key_cb = ttk.Combobox(form, state="readonly")
        self.key_cb.grid(row=2, column=1, sticky="ew", pady=6)
        self.key_cb.bind("<<ComboboxSelected>>", self._on_key_selected)

        ttk.Label(form, text="Backend").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        self.backend_cb = ttk.Combobox(form, state="readonly", values=["auto", "openssl", "cryptography"])
        self.backend_cb.grid(row=3, column=1, sticky="ew", pady=6)
        self.backend_cb.set("auto")
        self.backend_cb.bind("<<ComboboxSelected>>", lambda _evt: self._render_details())

        ttk.Label(form, text="Fisier").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=6)
        self.file_cb = ttk.Combobox(form, state="readonly")
        self.file_cb.grid(row=4, column=1, sticky="ew", pady=6)
        self.file_cb.bind("<<ComboboxSelected>>", self._on_file_selected)

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, pady=(8, 6))

        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Adauga fisier...", command=self.add_file).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Import cheie...", command=self.import_key).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Debug cheie...", command=self.debug_selected_key).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Encrypt", command=self.encrypt_selected).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Decrypt", command=self.decrypt_selected).pack(side=tk.LEFT)

        self.status = ttk.Label(root, text="")
        self.status.pack(fill=tk.X, pady=(8, 0))

        details = ttk.LabelFrame(root, text="Detalii selectie", padding=10)
        details.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.details_text = tk.Text(details, height=10, wrap="word")
        self.details_text.pack(fill=tk.BOTH, expand=True)
        self.details_text.configure(state="disabled")

    def _set_status(self, msg: str) -> None:
        self.status.configure(text=msg)

    def _set_details(self, msg: str) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", tk.END)
        self.details_text.insert(tk.END, msg)
        self.details_text.configure(state="disabled")

    def refresh(self) -> None:
        with self.Session() as session:
            self.algorithms = list(session.scalars(select(models.Algorithm).order_by(models.Algorithm.created_at.desc())))
            self.variants = list(
                session.scalars(select(models.AlgorithmVariant).order_by(models.AlgorithmVariant.created_at.desc()))
            )
            self.keys = list(session.scalars(select(models.Key).order_by(models.Key.created_at.desc())))
            self.files = list(session.scalars(select(models.File).order_by(models.File.created_at.desc())))

        self._update_algorithm_cb()
        self._update_variant_cb()
        self._update_key_cb()
        self._update_file_cb()
        self._sync_backend_cb()
        self._render_details()
        self._set_status("Incarcat din DB.")

    def _get_file_artifact_by_type(self, *, file_id: uuid.UUID, artifact_type_name: str) -> models.FileArtifact | None:
        with self.Session() as session:
            artifact_type = session.scalar(
                select(models.ArtifactType).where(models.ArtifactType.name == artifact_type_name)
            )
            if not artifact_type:
                return None
            stmt = (
                select(models.FileArtifact)
                .where(
                    models.FileArtifact.file_id == file_id,
                    models.FileArtifact.artifact_type_id == artifact_type.id,
                )
                .order_by(models.FileArtifact.created_at.desc())
            )
            return session.scalar(stmt)

    def _latest_operation_for_selection(self) -> models.CryptoOperation | None:
        with self.Session() as session:
            stmt = select(models.CryptoOperation)
            if self.selected_file is not None:
                stmt = stmt.where(models.CryptoOperation.file_id == self.selected_file.id)
            elif self.selected_key is not None:
                stmt = stmt.where(models.CryptoOperation.key_id == self.selected_key.id)
            else:
                return None

            stmt = stmt.order_by(models.CryptoOperation.started_at.desc())
            return session.scalar(stmt)

    def encrypt_selected(self) -> None:
        if not self.selected_file:
            messagebox.showerror("KLM", "Selecteaza un fisier.")
            return
        if not self.selected_variant:
            messagebox.showerror("KLM", "Selecteaza o varianta de algoritm.")
            return
        if not self.selected_key:
            messagebox.showerror("KLM", "Selecteaza o cheie.")
            return

        # input artifact (decrypted) gives us the real file path
        input_artifact = self._get_file_artifact_by_type(file_id=self.selected_file.id, artifact_type_name="decrypted")
        if not input_artifact:
            messagebox.showerror(
                "KLM",
                "Nu exista artifact de tip 'decrypted' pentru fisierul selectat. Foloseste 'Adauga fisier...' primul.",
            )
            return

        try:
            with self.Session() as session:
                service = CryptoService(session=session)
                out_id = service.encrypt_file(
                    file_path=input_artifact.path,
                    key_id=self.selected_key.id,
                    algorithm_variant=self.selected_variant.name,
                    params={
                        "crypto_backend": self.backend_cb.get(),
                        "file_id": str(self.selected_file.id),
                        "algorithm_variant_id": str(self.selected_variant.id),
                        "input_artifact_id": str(input_artifact.id),
                    },
                )
                session.commit()
                out_artifact = session.get(models.FileArtifact, out_id)

            self.refresh()
            self._set_status(f"Encrypt OK: {out_artifact.path if out_artifact else out_id}")
        except NotImplementedError as exc:
            messagebox.showinfo("KLM - encrypt", str(exc) or "Encrypt: not implemented yet.")
        except Exception as exc:
            messagebox.showerror("KLM - encrypt", str(exc))

    def decrypt_selected(self) -> None:
        if not self.selected_file:
            messagebox.showerror("KLM", "Selecteaza un fisier.")
            return
        if not self.selected_key:
            messagebox.showerror("KLM", "Selecteaza o cheie.")
            return

        input_artifact = self._get_file_artifact_by_type(file_id=self.selected_file.id, artifact_type_name="encrypted")
        if not input_artifact:
            messagebox.showerror(
                "KLM",
                "Nu exista artifact de tip 'encrypted' pentru fisierul selectat. Ruleaza mai intai Encrypt.",
            )
            return

        try:
            with self.Session() as session:
                service = CryptoService(session=session)
                out_id = service.decrypt_file(
                    artifact_id=input_artifact.id,
                    key_id=self.selected_key.id,
                    params={
                        "crypto_backend": self.backend_cb.get(),
                        **({"algorithm_variant_id": str(self.selected_variant.id)} if self.selected_variant else {}),
                    },
                )
                session.commit()
                out_artifact = session.get(models.FileArtifact, out_id)

            self.refresh()
            self._set_status(f"Decrypt OK: {out_artifact.path if out_artifact else out_id}")
        except NotImplementedError as exc:
            messagebox.showinfo("KLM - decrypt", str(exc) or "Decrypt: not implemented yet.")
        except Exception as exc:
            messagebox.showerror("KLM - decrypt", str(exc))

    def _update_algorithm_cb(self) -> None:
        labels = [a.name for a in self.algorithms]
        self.algorithm_cb["values"] = labels
        if self.selected_algorithm and self.selected_algorithm.name in labels:
            self.algorithm_cb.set(self.selected_algorithm.name)
        elif labels:
            self.algorithm_cb.current(0)
            self._on_algorithm_selected()

    def _filtered_variants(self) -> list[models.AlgorithmVariant]:
        if not self.selected_algorithm:
            return []
        return [v for v in self.variants if v.algorithm_id == self.selected_algorithm.id]

    def _update_variant_cb(self) -> None:
        variants = self._filtered_variants()
        labels = [v.name for v in variants]
        self.variant_cb["values"] = labels
        if self.selected_variant and self.selected_variant.name in labels:
            self.variant_cb.set(self.selected_variant.name)
        else:
            self.selected_variant = variants[0] if variants else None
            if labels:
                self.variant_cb.current(0)
            else:
                self.variant_cb.set("")
        self._sync_backend_cb()
        self._update_key_cb()

    def _allowed_backends_for_variant(self) -> list[str]:
        if not self.selected_variant:
            return ["auto", "openssl", "cryptography"]

        variant_name = self.selected_variant.name.upper()
        if variant_name.endswith("-GCM") or variant_name.endswith("-CCM"):
            return ["auto", "cryptography"]
        return ["auto", "openssl", "cryptography"]

    def _sync_backend_cb(self) -> None:
        allowed = self._allowed_backends_for_variant()
        current = self.backend_cb.get() if hasattr(self, "backend_cb") else "auto"
        self.backend_cb["values"] = allowed
        if current not in allowed:
            replacement = "cryptography" if "cryptography" in allowed and "openssl" not in allowed else "auto"
            self.backend_cb.set(replacement)
            if self.selected_variant:
                self._set_status(
                    f"Backend ajustat automat la '{replacement}' pentru varianta {self.selected_variant.name}."
                )
        elif not current:
            self.backend_cb.set("auto")

    def _filtered_keys(self) -> list[models.Key]:
        if not self.selected_variant:
            return []
        return [k for k in self.keys if k.algorithm_id == self.selected_variant.id]

    def _update_key_cb(self) -> None:
        keys = self._filtered_keys()
        labels = [k.name for k in keys]
        self.key_cb["values"] = labels
        if self.selected_key and self.selected_key.name in labels:
            self.key_cb.set(self.selected_key.name)
        else:
            self.selected_key = keys[0] if keys else None
            if labels:
                self.key_cb.current(0)
            else:
                self.key_cb.set("")

    def _update_file_cb(self) -> None:
        labels = [f.name for f in self.files]
        self.file_cb["values"] = labels
        if self.selected_file and self.selected_file.name in labels:
            self.file_cb.set(self.selected_file.name)
        else:
            self.selected_file = self.files[0] if self.files else None
            if labels:
                self.file_cb.current(0)
            else:
                self.file_cb.set("")

    def _on_algorithm_selected(self, _evt=None) -> None:
        name = self.algorithm_cb.get()
        self.selected_algorithm = next((a for a in self.algorithms if a.name == name), None)
        self.selected_variant = None
        self.selected_key = None
        self._update_variant_cb()
        self._render_details()

    def _on_variant_selected(self, _evt=None) -> None:
        name = self.variant_cb.get()
        variants = self._filtered_variants()
        self.selected_variant = next((v for v in variants if v.name == name), None)
        self.selected_key = None
        self._sync_backend_cb()
        self._update_key_cb()
        self._render_details()

    def _on_key_selected(self, _evt=None) -> None:
        name = self.key_cb.get()
        keys = self._filtered_keys()
        self.selected_key = next((k for k in keys if k.name == name), None)
        self._render_details()

    def _on_file_selected(self, _evt=None) -> None:
        name = self.file_cb.get()
        self.selected_file = next((f for f in self.files if f.name == name), None)
        self._render_details()

    def debug_selected_key(self) -> None:
        if not self.selected_key:
            messagebox.showerror("KLM", "Selecteaza o cheie.")
            return
        _DebugKeyDialog(self, self.selected_key.id)

    def _render_details(self) -> None:
        parts: list[str] = []
        if self.selected_algorithm:
            parts.append(f"Algoritm: {self.selected_algorithm.name} ({self.selected_algorithm.id})")
        else:
            parts.append("Algoritm: -")

        if self.selected_variant:
            parts.append(f"Varianta: {self.selected_variant.name} ({self.selected_variant.id})")
        else:
            parts.append("Varianta: -")

        if self.selected_key:
            parts.append(f"Cheie: {self.selected_key.name} ({self.selected_key.id})")
            parts.append(f"  status: {self.selected_key.status}")
            parts.append(f"  format material: {self.selected_key.material_format}")
            parts.append(f"  schema stocare: {self.selected_key.encryption_scheme}")
            parts.append(f"  creata la: {self.selected_key.created_at}")
            parts.append(f"  expira la: {self.selected_key.expires_at or '-'}")
            parts.append(f"  params criptare: {self.selected_key.encryption_params}")
            parts.append("  material cheie: ascuns in panoul principal; foloseste 'Debug cheie...'")
        else:
            parts.append("Cheie: -")

        if self.selected_file:
            parts.append(f"Fisier: {self.selected_file.name} ({self.selected_file.id})")
        else:
            parts.append("Fisier: -")

        backend = self.backend_cb.get() if hasattr(self, "backend_cb") else "auto"
        parts.append(f"Backend selectat: {backend}")
        if self.selected_variant:
            allowed = ", ".join(self._allowed_backends_for_variant())
            parts.append(f"Backend-uri permise pentru varianta curenta: {allowed}")

        latest_operation = self._latest_operation_for_selection()
        if latest_operation:
            with self.Session() as session:
                provider = session.get(models.CryptoProvider, latest_operation.provider_id)
                result = session.get(models.ResultType, latest_operation.result_type_id)
                op_type = session.get(models.CryptoOperationType, latest_operation.operation_type_id)

            provider_label = provider.name if provider else str(latest_operation.provider_id)
            if provider and provider.version:
                provider_label = f"{provider_label} {provider.version}"

            operation_backend = latest_operation.params.get("crypto_backend", "-")
            parts.append("Ultima operatie relevanta:")
            parts.append(f"  tip: {op_type.name if op_type else latest_operation.operation_type_id}")
            parts.append(f"  provider: {provider_label}")
            parts.append(f"  backend: {operation_backend}")
            parts.append(f"  rezultat: {result.name if result else latest_operation.result_type_id}")
            parts.append(f"  start: {latest_operation.started_at}")
            parts.append(f"  end: {latest_operation.ended_at or '-'}")
        else:
            parts.append("Ultima operatie relevanta: -")

        self._set_details("\n".join(parts))

    def add_file(self) -> None:
        path = filedialog.askopenfilename(title="Selecteaza un fisier")
        if not path:
            return

        p = Path(path)
        size_bytes = os.path.getsize(path)
        digest = _sha256_file(path)
        artifact_type_name = "decrypted"
        original_name = p.name
        base_name = p.stem

        if p.suffix.lower() == ".enc":
            try:
                meta = _load_artifact_metadata(p)
            except FileNotFoundError:
                self._set_status(
                    f"Eroare: pentru fisierul criptat '{p.name}' lipseste sidecar-ul .meta necesar la decrypt."
                )
                return
            except json.JSONDecodeError as exc:
                self._set_status(f"Eroare: fisierul .meta pentru '{p.name}' nu este JSON valid: {exc}")
                return

            artifact_type_name = "encrypted"
            original_name = str(meta.get("original_name") or p.stem)
            base_name = Path(original_name).stem or p.stem

        with self.Session() as session:
            existing_names = set(session.scalars(select(models.File.name)))
            name = _unique_name(existing_names, base_name)

            file_row = models.File(
                name=name,
                original_name=original_name,
                original_size_bytes=size_bytes,
                original_hash=digest,
            )
            session.add(file_row)
            session.flush()

            artifact_type = _get_or_create_by_name(session, models.ArtifactType, artifact_type_name)
            artifact = models.FileArtifact(
                file_id=file_row.id,
                artifact_type_id=artifact_type.id,
                path=str(p),
                size_bytes=size_bytes,
                hash=digest,
            )
            session.add(artifact)
            session.commit()

        self.refresh()
        self._set_status(f"Fisier adaugat: {name} ({artifact_type_name})")

    def import_key(self) -> None:
        dialog = _ImportKeyDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return

        payload = dialog.result

        with self.Session() as session:
            key_type = session.get(models.KeyType, payload.type_id)
            usage = session.get(models.KeyUsage, payload.usage_id)
            variant = session.get(models.AlgorithmVariant, payload.variant_id)
            if not key_type or not usage or not variant:
                self._set_status("Eroare: tip/usage/varianta invalida (nu exista in DB).")
                return

            if session.scalar(select(models.Key).where(models.Key.name == payload.name)) is not None:
                self._set_status(f"Eroare: exista deja o cheie cu numele '{payload.name}'.")
                return

            try:
                material_plain = base64.b64decode(payload.encrypted_material_b64, validate=True)
            except Exception:
                self._set_status("Eroare: encrypted_material nu e Base64 valid.")
                return

            # Store key material encrypted (app-level) so CryptoService can use it.
            from klm.services.crypto_service import _encrypt_bytes_with_master

            try:
                encrypted_material, enc_params = _encrypt_bytes_with_master(material_plain)
            except Exception as exc:
                self._set_status(f"Eroare: nu pot cripta materialul cheii pentru stocare: {exc}")
                return

            key = models.Key(
                name=payload.name,
                type_id=payload.type_id,
                algorithm_id=payload.variant_id,
                status="active",
                usage_id=payload.usage_id,
                encrypted_material=encrypted_material,
                material_format="raw",
                encryption_scheme="app-level-aes-256-cbc",
                encryption_params=enc_params,
            )
            session.add(key)
            session.commit()

        self.refresh()
        self._set_status(f"Cheie importata: {payload.name}")


@dataclass(frozen=True)
class ImportKeyPayload:
    name: str
    type_id: uuid.UUID
    usage_id: uuid.UUID
    variant_id: uuid.UUID
    encrypted_material_b64: str


class _DebugKeyDialog(tk.Toplevel):
    def __init__(self, app: KLMApp, key_id: uuid.UUID) -> None:
        super().__init__(app)
        self.app = app
        self.key_id = key_id

        self.title("Debug cheie")
        self.geometry("760x620")
        self.minsize(720, 520)

        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        header = ttk.Label(
            root,
            text="Inspectare cheie selectata",
            font=("Segoe UI", 12, "bold"),
        )
        header.grid(row=0, column=0, sticky="w")

        info = ttk.Label(
            root,
            text=(
                "Debug only: materialul cheii nu este afisat automat. "
                "Apasa butonul de mai jos pentru a-l obtine temporar din DB."
            ),
            wraplength=700,
            justify="left",
        )
        info.grid(row=1, column=0, sticky="ew", pady=(8, 10))

        panes = ttk.Panedwindow(root, orient=tk.VERTICAL)
        panes.grid(row=2, column=0, sticky="nsew")

        meta_frame = ttk.Labelframe(panes, text="Metadate cheie", padding=10)
        panes.add(meta_frame, weight=1)
        meta_frame.columnconfigure(0, weight=1)

        self.meta_text = tk.Text(meta_frame, height=13, wrap="word")
        self.meta_text.pack(fill=tk.BOTH, expand=True)
        self.meta_text.configure(state="disabled")

        material_frame = ttk.Labelframe(panes, text="Material cheie", padding=10)
        panes.add(material_frame, weight=1)
        material_frame.columnconfigure(0, weight=1)

        actions = ttk.Frame(material_frame)
        actions.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(actions, text="Obtine materialul cheii", command=self._load_material).pack(side=tk.LEFT)
        ttk.Button(actions, text="Copiaza Base64", command=self._copy_base64).pack(side=tk.LEFT, padx=8)

        self.material_text = tk.Text(material_frame, height=16, wrap="word")
        self.material_text.pack(fill=tk.BOTH, expand=True)
        self.material_text.configure(state="disabled")

        self._material_b64 = ""
        self._render_metadata()

        self.transient(app)
        self.grab_set()

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, value)
        widget.configure(state="disabled")

    def _render_metadata(self) -> None:
        with self.app.Session() as session:
            key = session.get(models.Key, self.key_id)
            if not key:
                self._set_text(self.meta_text, "Cheia nu mai exista in DB.")
                return

            key_type = session.get(models.KeyType, key.type_id)
            usage = session.get(models.KeyUsage, key.usage_id)
            variant = session.get(models.AlgorithmVariant, key.algorithm_id)
            algorithm = session.get(models.Algorithm, variant.algorithm_id) if variant else None

        parts = [
            f"Nume: {key.name}",
            f"ID: {key.id}",
            f"Status: {key.status}",
            f"Tip: {key_type.name if key_type else key.type_id}",
            f"Usage: {usage.name if usage else key.usage_id}",
            f"Algoritm: {algorithm.name if algorithm else '-'}",
            f"Varianta: {variant.name if variant else key.algorithm_id}",
            f"Creata la: {key.created_at}",
            f"Expira la: {key.expires_at or '-'}",
            f"Material format: {key.material_format}",
            f"Encryption scheme: {key.encryption_scheme}",
            f"Encryption params: {key.encryption_params}",
            f"Ciphertext bytes in DB: {len(bytes(key.encrypted_material))}",
        ]
        self._set_text(self.meta_text, "\n".join(parts))

    def _load_material(self) -> None:
        with self.app.Session() as session:
            key = session.get(models.Key, self.key_id)
            if not key:
                messagebox.showerror("KLM - debug cheie", "Cheia nu mai exista in DB.", parent=self)
                return

            service = CryptoService(session=session)
            try:
                material = service._get_key_bytes(key)
            except Exception as exc:
                messagebox.showerror("KLM - debug cheie", str(exc), parent=self)
                return

        self._material_b64 = base64.b64encode(material).decode("ascii")
        hex_material = material.hex()
        try:
            utf8_preview = material.decode("utf-8")
        except UnicodeDecodeError:
            utf8_preview = "<non-UTF8 binary>"

        rendered = "\n".join([
            "Base64:",
            self._material_b64,
            "",
            "Hex:",
            hex_material,
            "",
            "UTF-8 preview:",
            utf8_preview,
        ])
        self._set_text(self.material_text, rendered)

    def _copy_base64(self) -> None:
        if not self._material_b64:
            messagebox.showinfo(
                "KLM - debug cheie",
                "Obtine mai intai materialul cheii pentru a-l copia.",
                parent=self,
            )
            return
        self.clipboard_clear()
        self.clipboard_append(self._material_b64)
        messagebox.showinfo("KLM - debug cheie", "Base64 copiat in clipboard.", parent=self)


class _ImportKeyDialog(tk.Toplevel):
    def __init__(self, app: KLMApp) -> None:
        super().__init__(app)
        self.title("Import cheie")
        self.geometry("560x420")
        self.resizable(False, False)
        self.result: ImportKeyPayload | None = None

        self.app = app

        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="Nume cheie").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        self.name_entry = ttk.Entry(root)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(root, text="Tip cheie").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        self.type_cb = ttk.Combobox(root, state="readonly")
        self.type_cb.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(root, text="Usage").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.usage_cb = ttk.Combobox(root, state="readonly")
        self.usage_cb.grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(root, text="Varianta algoritm").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        self.variant_cb = ttk.Combobox(root, state="readonly")
        self.variant_cb.grid(row=3, column=1, sticky="ew", pady=6)

        ttk.Label(root, text="encrypted_material (Base64)").grid(
            row=4, column=0, sticky="nw", padx=(0, 10), pady=6
        )
        self.material_text = tk.Text(root, height=10, wrap="word")
        self.material_text.grid(row=4, column=1, sticky="ew", pady=6)

        btns = ttk.Frame(root)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Anuleaza", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Import", command=self._on_import).pack(side=tk.RIGHT, padx=8)

        self._load_lookups()

    def _load_lookups(self) -> None:
        with self.app.Session() as session:
            key_types = list(session.scalars(select(models.KeyType).order_by(models.KeyType.name.asc())))
            usages = list(session.scalars(select(models.KeyUsage).order_by(models.KeyUsage.name.asc())))
            variants = list(session.scalars(select(models.AlgorithmVariant).order_by(models.AlgorithmVariant.name.asc())))

        self._key_types = key_types
        self._usages = usages
        self._variants = variants

        self.type_cb["values"] = [t.name for t in key_types]
        self.usage_cb["values"] = [u.name for u in usages]
        self.variant_cb["values"] = [v.name for v in variants]

        if key_types:
            self.type_cb.current(0)
        if usages:
            self.usage_cb.current(0)
        if variants:
            # preselect current variant from main window if possible
            current = self.app.selected_variant
            if current and current.name in self.variant_cb["values"]:
                self.variant_cb.set(current.name)
            else:
                self.variant_cb.current(0)

    def _on_import(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            return

        type_name = self.type_cb.get()
        usage_name = self.usage_cb.get()
        variant_name = self.variant_cb.get()
        material_b64 = self.material_text.get("1.0", tk.END).strip()
        if not material_b64:
            return

        key_type = next((t for t in self._key_types if t.name == type_name), None)
        usage = next((u for u in self._usages if u.name == usage_name), None)
        variant = next((v for v in self._variants if v.name == variant_name), None)
        if not key_type or not usage or not variant:
            return

        self.result = ImportKeyPayload(
            name=name,
            type_id=key_type.id,
            usage_id=usage.id,
            variant_id=variant.id,
            encrypted_material_b64=material_b64,
        )
        self.destroy()


def run() -> None:
    try:
        app = KLMApp()
    except RuntimeError as exc:
        # Most common: DATABASE_URL missing.
        root = tk.Tk()
        root.withdraw()
        msg = str(exc)
        if msg == "DATABASE_URL is not set":
            msg = (
                "DATABASE_URL nu este setat.\n\n"
                "1) Copiaza .env.example -> .env\n"
                "2) Seteaza DATABASE_URL in .env (ex: postgresql+psycopg://user:pass@localhost:5432/klm)\n\n"
                "Apoi ruleaza din nou: python -m klm"
            )
        messagebox.showerror("KLM - configurare DB", msg)
        root.destroy()
        return

    except OperationalError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "KLM - conexiune DB",
            (
                "Nu ma pot conecta la baza de date (OperationalError).\n\n"
                "Cauze frecvente:\n"
                "- user/parola gresite in DATABASE_URL\n"
                "- Postgres nu ruleaza / port gresit\n\n"
                "Verifica DATABASE_URL din .env.\n\n"
                f"Detalii: {exc.orig if hasattr(exc, 'orig') else exc}"
            ),
        )
        root.destroy()
        return

    except SQLAlchemyError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "KLM - eroare DB",
            (
                "A aparut o eroare SQLAlchemy la initializarea UI-ului.\n\n"
                "Detalii: " + str(exc)
            ),
        )
        root.destroy()
        return

    app.mainloop()
