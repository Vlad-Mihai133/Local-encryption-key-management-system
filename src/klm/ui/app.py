from __future__ import annotations

import base64
import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, ttk

from sqlalchemy import select

from klm.db import models
from klm.db.session import create_db_engine, create_session_factory


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

        ttk.Label(form, text="Fisier").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        self.file_cb = ttk.Combobox(form, state="readonly")
        self.file_cb.grid(row=3, column=1, sticky="ew", pady=6)
        self.file_cb.bind("<<ComboboxSelected>>", self._on_file_selected)

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, pady=(8, 6))

        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Adauga fisier...", command=self.add_file).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Import cheie...", command=self.import_key).pack(side=tk.LEFT)

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
        self._render_details()
        self._set_status("Incarcat din DB.")

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
        self._update_key_cb()

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
        else:
            parts.append("Cheie: -")

        if self.selected_file:
            parts.append(f"Fisier: {self.selected_file.name} ({self.selected_file.id})")
        else:
            parts.append("Fisier: -")

        self._set_details("\n".join(parts))

    def add_file(self) -> None:
        path = filedialog.askopenfilename(title="Selecteaza un fisier")
        if not path:
            return

        p = Path(path)
        original_name = p.name
        size_bytes = os.path.getsize(path)
        digest = _sha256_file(path)

        with self.Session() as session:
            existing_names = set(session.scalars(select(models.File.name)))
            base_name = p.stem
            name = _unique_name(existing_names, base_name)

            file_row = models.File(
                name=name,
                original_name=original_name,
                original_size_bytes=size_bytes,
                original_hash=digest,
            )
            session.add(file_row)
            session.flush()

            artifact_type = _get_or_create_by_name(session, models.ArtifactType, "decrypted")
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
        self._set_status(f"Fisier adaugat: {name}")

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
                material = base64.b64decode(payload.encrypted_material_b64, validate=True)
            except Exception:
                self._set_status("Eroare: encrypted_material nu e Base64 valid.")
                return

            key = models.Key(
                name=payload.name,
                type_id=payload.type_id,
                algorithm_id=payload.variant_id,
                status="active",
                usage_id=payload.usage_id,
                encrypted_material=material,
                material_format="raw",
                encryption_scheme="import",
                encryption_params={},
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
    app = KLMApp()
    app.mainloop()
