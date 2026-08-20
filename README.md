# Data Catalog Scanner

A small, honest version of what a data-catalog product actually does: scan
heterogeneous data sources, normalize their schemas into one common metadata
model, and serve that catalog over an API for searching.

```
1. seed (Python)     loads real data into three "source" systems: a
                      Postgres schema, a SQLite file, and a MySQL database.
2. scanner (Python)  introspects all three sources, normalizes their
                      schemas, and writes the result into a catalog schema
                      (catalog.tables / catalog.columns) in Postgres.
3. api (Go)          reads the catalog schema and serves it over REST.
4. web (TypeScript)  a read-only Next.js browser on top of the API.
```

## Why three source types

The actual hard part of a scanner isn't querying one database -- it's that
every source exposes its schema through a completely different mechanism.
This project deliberately scans three:

- **PostgreSQL** (`source_realestate` schema) -- introspected via
  `information_schema`, including a real primary-key lookup and an actual
  foreign key (`transactions.ward -> ward_population.ward`).
- **SQLite** (`tokyo_anaba.sqlite`) -- introspected via `PRAGMA table_info`,
  which reports primary keys and nullability in a totally different shape
  than `information_schema` does.
- **MySQL** (`dblp_demo` database) -- also has an `information_schema`, but
  it isn't a drop-in copy of Postgres's: primary keys show up directly on
  `information_schema.columns` (`COLUMN_KEY='PRI'`) instead of needing the
  constraint-table join Postgres requires, identifiers are quoted with
  backticks instead of double quotes, and casting to text for min/max is
  `CAST(col AS CHAR)` rather than `::text` or `CAST(col AS TEXT)`. Adding
  this third connector was the actual test of whether `Connector` (see
  `scanner/src/scanner/connectors/base.py`) generalizes, or was
  accidentally designed around Postgres/SQLite's specific quirks.

All three get normalized into the same `TableMetadata`/`ColumnMetadata`
model (`scanner/src/scanner/models.py`) before being written to the catalog,
so the API layer never has to know which engine a table actually came from.

The source data is real, not generated, for all three:
`source_realestate` is an actual real-estate transaction dataset
(千代田区・文京区, 2021-2025) from another one of my projects, the SQLite
source is the spots/areas data from a Tokyo congestion-mapping app I built,
and the MySQL source (`dblp_demo`) is a real, connected slice of the DBLP
co-authorship graph -- a 5-hop breadth-first search from the actual
Meltdown vulnerability paper (`tr/meltdown/s18`), using a cached graph from
a fourth project of mine (`bipartite-layout`). The authors are real
published researchers (Daniel Genkin, Moritz Lipp, Paul Kocher, Yuval
Yarom, among the actual co-authors of the Meltdown/Spectre papers), not
placeholder names. Reusing real data with real irregularities felt more
honest than a generic sample database.

## Running it

```bash
docker compose up
```

This runs the whole pipeline in order: brings up Postgres, seeds both
source systems with data, scans them into the catalog, starts the API on
`:8080`, then starts the web UI on `:3000`.

```bash
curl http://localhost:8080/api/tables
curl http://localhost:8080/api/tables/1
curl "http://localhost:8080/api/search?q=congestion"
```

`search` matches against table names *and* column names (via a correlated
`EXISTS`), since searching by column is usually the more useful query in a
real catalog -- `q=congestion` finds both `areas` and `spots` because they
both have a `congestion` column, even though neither table name mentions it.

## Browsing the catalog

`web/` is a minimal Next.js app: a table list with search, and a detail page
showing each column's structure and profile stats. A few decisions worth
explaining:

- **Server Components, not a client-side fetch.** Every page is an async
  Server Component that calls the Go API directly during rendering --
  there's no `"use client"`/`useEffect`/loading-spinner dance anywhere,
  because this is a read-only catalog browser with no client state to
  manage. The practical payoff: the browser never talks to the API
  directly, only the Next.js server does, so the Go API needs zero CORS
  configuration.
- **Search is a plain `<form method="GET">`.** Submitting it is just a
  normal navigation to `/?q=...`, which Next reads out of `searchParams`
  server-side. No client JS needed for that either.
- **`getTable` returns `null` on a 404**, rather than throwing, so the page
  can call Next's `notFound()` and render a real not-found view instead of
  a generic error boundary swallowing the distinction between "this table
  doesn't exist" and "the API is down."

See `web/README.md` for how to run it.

## Column profiling

Beyond structure (type, nullability, primary key), each column also gets
profiled: `null_count`, `distinct_count`, `min_value`, `max_value`
(`ColumnProfile` in `scanner/src/scanner/models.py`). This is the difference
between "this column is TEXT" and "this column is TEXT, 1% NULL, mostly one
of four values" -- the latter is what actually tells you whether a column is
safe to join on or worth deduplicating.

All three connectors compute all four stats in **one query per table**, not
one per column -- an N+1 query pattern here would mean a table with 20
columns runs 20 separate scans of itself. `min_value`/`max_value` are
stored as text (`::text` in Postgres, `CAST(... AS TEXT)` in SQLite,
`CAST(... AS CHAR)` in MySQL -- three different syntaxes for the same idea)
rather than a typed value, for the same reason `data_type` is already a
plain string: the common model has to
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

## Four bugs worth mentioning

All four were caught by actually running the system end-to-end, not by
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

4. **A "healthy" MySQL container that still refused connections.**
   `docker compose up` failed once with `ConnectionRefusedError`
   immediately after compose reported the `mysql` service healthy. Cause:
   MySQL's first-boot sequence runs a temporary, socket-only instance to
   execute its own init scripts, then shuts it down and restarts the real
   instance with networking enabled -- and the healthcheck
   (`mysqladmin ping -h localhost`) resolves `localhost` to the Unix
   socket, so it reports "healthy" during that temporary instance, not
   the real one. Fixed two ways: the healthcheck now pings `127.0.0.1`
   (forces a real TCP check, so it can't pass against the socket-only
   instance), and `load_mysql_source.py` retries the connection a few
   times with a short delay regardless, since a compose healthcheck
   passing is a hint, not a guarantee, and the seed step should be able
   to ride out a few seconds of the DB not actually being ready yet.

## Tech stack

- **Python** (scanner, seed) -- `psycopg2` for Postgres, `PyMySQL` for
  MySQL (pure Python, no C client library needed), stdlib `sqlite3` for
  SQLite, `pytest` for tests
- **Go** (API) -- stdlib `net/http` with Go 1.22+ pattern routing (no router
  dependency), `pgx` for Postgres
- **TypeScript** (web) -- Next.js App Router, Server Components only (no
  client-side data fetching), Tailwind CSS
- **PostgreSQL** as both a scan target and the catalog store; **MySQL** and
  **SQLite** as additional scan targets
- **Docker Compose** to wire the pipeline together

## Tests

```bash
cd scanner && pytest -v                 # needs TEST_POSTGRES_DSN and
                                         # TEST_MYSQL_HOST(+TEST_MYSQL_ROOT_PASSWORD)
                                         # for those two connectors' tests;
                                         # SQLite tests run standalone
cd api && go test ./... -v              # handler tests use a fake Store,
                                         # no database needed
```

CI (`.github/workflows/ci.yml`) runs both suites -- the scanner's Postgres
*and* MySQL tests against real service containers, neither skipped -- plus
`web-checks` (lint/test/build) and a full `docker compose build`.
