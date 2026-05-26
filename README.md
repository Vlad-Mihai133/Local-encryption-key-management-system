# Local Key Management (KLM)

Sprint 1 deliverables:
- Postgres schema (UUID primary keys)
- SQLAlchemy entities + repository layer
- Crypto service for key generation, file encrypt/decrypt and key-material protection in DB
- CLI and Tkinter UI for working with files, keys and backend selection

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

Nota: `schema.sql` face seed doar pentru tabelele de tip lookup (ex. key_types, key_usages, algorithm_types etc.).
Tabelele `algorithms` si `algorithm_variants` NU sunt populate implicit, deci UI-ul va afisa liste goale pana le seed-uiesti.

Seed demo (AES/RSA + cateva variante):

```powershell
psql -d klm -f .\sql\seed_demo_algorithms.sql
```

Cleanup pentru variante demo legacy (de exemplu `AES-128-GCM`, daca exista intr-o baza veche si vrei sa o elimini in siguranta):

```powershell
psql -d klm -f .\sql\cleanup_legacy_demo_variants.sql
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

## Running (CLI)

CLI-ul poate rula operatii pentru artifacts, keygen, encrypt si decrypt.

Because the project uses a `src/` layout, run with `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = "src"
python -m klm --help
```

Note: `python -m klm` (fara argumente) porneste UI-ul Tkinter; pentru CLI foloseste `--help` sau ruleaza direct:

```powershell
$env:PYTHONPATH = "src"
python -m klm.cli --help
```

Exemple pentru backend-ul de criptare al fisierelor:

```powershell
$env:PYTHONPATH = "src"
python -m klm.cli encrypt --file .\testfiles\test.txt.txt --key-id <UUID> --variant AES-256-CBC --backend openssl
python -m klm.cli encrypt --file .\testfiles\test.txt.txt --key-id <UUID> --variant AES-256-GCM --backend cryptography
```

## UI grafic (desktop, Tkinter)

UI-ul este o fereastra simpla pentru:
- selectare algoritm -> varianta
- selectare backend (`auto`, `openssl`, `cryptography`) pentru operatiile pe fisiere
- selectare/adaugare cheie (import de `encrypted_material` in Base64)
- selectare/adaugare fisier (browse + inregistrare in DB)
- debug pentru cheia selectata (metadate + obtinere material cheie la cerere)

Rulare:

```powershell
$env:PYTHONPATH = "src"
python -m klm
```

Necesita `DATABASE_URL` setat in `.env` (la fel ca pentru CLI).

## Schema note (keys.algorithm_id)

Schema din `sql/schema.sql` a fost aliniata cu ORM-ul: `keys.algorithm_id` refera `algorithm_variants(id)`.

Daca ai o baza de date veche (creata cu o schema unde `keys.algorithm_id` refera `algorithms(id)`), vezi scriptul:
- `sql/migrate_keys_algorithm_id_to_variants.sql`

## Notes

- Key material is stored encrypted in the DB and is decrypted in the service layer when needed.
- File encryption/decryption supports 2 backends: `openssl` and `cryptography`.
- In UI si CLI poti alege backend-ul explicit sau poti lasa `auto`; pentru variante AEAD precum `AES-256-GCM`, `auto` foloseste `cryptography`.
- Supported demo variants for file crypto are `AES-128-CBC`, `AES-192-CBC`, `AES-256-CBC`, `AES-256-CTR`, `AES-256-GCM`.
- Varianta `AES-256-GCM` este expusa in seed-ul demo si foloseste backend-ul `cryptography`, deoarece `openssl enc` nu suporta fluxul AEAD necesar pentru GCM.
