# Local Key Management (KLM)

Sprint 1 deliverables:
- Postgres schema (UUID primary keys)
- SQLAlchemy entities + repository stubs
- Placeholder service layer + CLI entrypoint

DB schema lives in `sql/schema.sql`.

## Requirements

- Python: 3.11+ (this repo uses modern Python syntax + SQLAlchemy 2.x)
- PostgreSQL: 14+ recommended
- Extensions: `pgcrypto` (enabled by the schema)

## Setup (Windows PowerShell)

### 1) Create database

Use your preferred Postgres install (local service / Docker / WSL). Then create a DB:

```powershell
createdb klm
```

### 2) Apply schema

The schema is idempotent (safe to re-run):

```powershell
psql -d klm -f .\sql\schema.sql
```

### 3) Python environment

Create a virtualenv with Python 3.11+:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt
```

### 4) Configure DB connection

Copy `.env.example` to `.env` and set `DATABASE_URL`

## Running (placeholder CLI)

This sprint the CLI is intentionally a placeholder (commands raise `NotImplementedError`).

Because the project uses a `src/` layout, run with `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = "src"
python -m klm --help
```

## UI grafic (desktop, Tkinter)

UI-ul este o fereastra simpla pentru:
- selectare algoritm -> varianta
- selectare/adaugare cheie (import de `encrypted_material` in Base64)
- selectare/adaugare fisier (browse + inregistrare in DB)

Rulare:

```powershell
$env:PYTHONPATH = "src"
python -m klm.ui
```

Necesita `DATABASE_URL` setat in `.env` (la fel ca pentru CLI).

## Schema note (keys.algorithm_id)

Schema din `sql/schema.sql` a fost aliniata cu ORM-ul: `keys.algorithm_id` refera `algorithm_variants(id)`.

Daca ai o baza de date veche (creata cu o schema unde `keys.algorithm_id` refera `algorithms(id)`), vezi scriptul:
- `sql/migrate_keys_algorithm_id_to_variants.sql`

## Notes

- Key material is stored in the DB (ciphertext).
- The encryption/decryption of key material is not implemented in Sprint 1; the future plan is documented in `src/klm/services/crypto_service.py`.
