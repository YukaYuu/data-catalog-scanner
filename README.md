# Data Catalog Scanner

A small, honest version of what a data-catalog product actually does: scan
heterogeneous data sources, normalize their schemas into one common metadata
model, and serve that catalog over an API for searching.

```
1. seed (Python)     loads real data into two "source" systems: a Postgres
                      schema and a SQLite file.
2. scanner (Python)  introspects both sources, normalizes their schemas,
                      and writes the result into a catalog schema
                      (catalog.tables / catalog.columns) in Postgres.
3. api (Go)          reads the catalog schema and serves it over REST.
```

## Why two source types

The actual hard part of a scanner isn't querying one database -- it's that
every source exposes its schema through a completely different mechanism.
This project deliberately scans two:

- **PostgreSQL** (`source_realestate` schema) -- introspected via
  `information_schema`, including a real primary-key lookup and an actual
  foreign key (`transactions.ward -> ward_population.ward`).
- **SQLite** (`tokyo_anaba.sqlite`) -- introspected via `PRAGMA table_info`,
  which reports primary keys and nullability in a totally different shape
  than `information_schema` does.

Both get normalized into the same `TableMetadata`/`ColumnMetadata` model
(`scanner/src/scanner/models.py`) before being written to the catalog, so the
API layer never has to know which engine a table actually came from.

The source data is real, not generated: `source_realestate` is an actual
real-estate transaction dataset (千代田区・文京区, 2021-2025) from another one
of my projects, and the SQLite source is the spots/areas data from a Tokyo
congestion-mapping app I built. Reusing real data with real irregularities
felt more honest than a generic sample database.

## Running it

```bash
docker compose up
```

This runs the whole pipeline in order: brings up Postgres, seeds both
source systems with data, scans them into the catalog, then starts the API
on `:8080`.

```bash
curl http://localhost:8080/api/tables
curl http://localhost:8080/api/tables/1
curl "http://localhost:8080/api/search?q=congestion"
```

`search` matches against table names *and* column names (via a correlated
`EXISTS`), since searching by column is usually the more useful query in a
real catalog -- `q=congestion` finds both `areas` and `spots` because they
both have a `congestion` column, even though neither table name mentions it.

## Column profiling

Beyond structure (type, nullability, primary key), each column also gets
profiled: `null_count`, `distinct_count`, `min_value`, `max_value`
(`ColumnProfile` in `scanner/src/scanner/models.py`). This is the difference
between "this column is TEXT" and "this column is TEXT, 1% NULL, mostly one
of four values" -- the latter is what actually tells you whether a column is
safe to join on or worth deduplicating.

Both connectors compute all four columns in **one query per table**, not one
per column -- an N+1 query pattern here would mean a table with 20 columns
runs 20 separate scans of itself. `min_value`/`max_value` are stored as text
(`CAST(...  AS TEXT)` / `::text`) rather than a typed value, for the same
reason `data_type` is already a plain string: the common model has to
represent every SQL type uniformly, and a typed union would leak
engine-specific type systems back into the API layer this project is trying
to keep engine-agnostic.

This is also what actually found a real data-quality bug, not a synthetic
one: `building_structure` in the real-estate source had 38 rows where the
value was the literal text `"NaN"` instead of a real `NULL`. The seed
loader's numeric columns were all guarded with `pd.notna(...)`, but the
free-text columns (`district`, `nearest_station`, `floor_plan`,
`building_structure`) used `row.get(...)` unguarded -- so a missing
value stayed as pandas' `float('nan')`, and psycopg2 happily inserted that
into a `TEXT` column as the literal string `"NaN"` instead of `NULL`. Profiling
surfaced it immediately: `building_structure`'s `min_value` was `"NaN"`
(sorts before any Japanese text). Fixed in `seed-data/load_postgres_source.py`
by adding the same `pd.notna(...)` guard to all four text columns.

## Three bugs worth mentioning

All three were caught by actually running the system end-to-end, not by
inspection:

1. **NULL isn't equal to NULL for uniqueness.** The catalog's dedup key is
   `(source_name, schema_name, table_name)`, and SQLite sources don't have a
   schema, so `schema_name` seemed like it should be `NULL` there. But
   Postgres treats every `NULL` as distinct from every other `NULL` for
   `UNIQUE`/`ON CONFLICT` purposes -- so re-scanning a schema-less source
   would silently insert duplicate rows instead of updating existing ones.
   Fixed by storing `''` instead of `NULL` for those sources
   (`scanner/src/scanner/catalog_store.py`).

2. **The seed step wasn't idempotent.** Compose's dependency resolution
   re-runs already-completed one-shot services when you bring up a service
   that depends on them (e.g. starting `api` on its own re-triggers `seed`
   and `scanner`). The Postgres loader had no guard against running twice --
   it doubled every transaction row (7514 instead of 3757) on a second run.
   `ward_population` was already safe (`ON CONFLICT ... DO NOTHING` on a real
   key), but `transactions` has no natural key to dedup rows on, so it now
   truncates and reloads instead (`seed-data/load_postgres_source.py`).

3. **Missing values became the literal text `"NaN"`.** See "Column
   profiling" above -- four free-text columns in the seed loader lacked the
   `pd.notna(...)` guard the numeric columns had, so pandas' NaN reached
   Postgres unconverted and landed in a `TEXT` column as a real, searchable
   `"NaN"` string instead of `NULL`.

## Tech stack

- **Python** (scanner, seed) -- `psycopg2` for Postgres, stdlib `sqlite3`
  for SQLite, `pytest` for tests
- **Go** (API) -- stdlib `net/http` with Go 1.22+ pattern routing (no router
  dependency), `pgx` for Postgres
- **PostgreSQL** as both a scan target and the catalog store
- **Docker Compose** to wire the pipeline together

## Tests

```bash
cd scanner && pytest -v                 # needs TEST_POSTGRES_DSN for the
                                         # Postgres connector test; SQLite
                                         # tests run standalone
cd api && go test ./... -v              # handler tests use a fake Store,
                                         # no database needed
```

CI (`.github/workflows/ci.yml`) runs both suites -- the scanner's Postgres
test against a real Postgres service container, not skipped -- plus a full
`docker compose build`.
