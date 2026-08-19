# Catalog Web

A minimal read-only browser for the catalog: a table list with search, and
a table detail page showing each column's structure and profile stats
(null count, distinct count, min/max). See the root
[README](../README.md#browsing-the-catalog) for the design rationale
(why Server Components, why no CORS on the Go API, etc).

## Running it

Via `docker compose up` from the repo root (recommended -- wires up the
whole pipeline including this service). To run standalone against an
already-running API:

```bash
cp .env.example .env.local   # point CATALOG_API_URL at your API instance
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).
