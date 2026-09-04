# Prepared data

The raw source snapshots are preserved in `data/raw/` and the joined, filtered
application dataset is preserved in `data/prepared/`.

## Provenance

- Downloaded: 2026-09-04
- Constituents source: `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv`
- Requested financials source: `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents-financials.csv`
- Financials fallback used: `https://raw.githubusercontent.com/datasets/s-and-p-500-companies-financials/main/data/constituents-financials.csv`
- Raw row counts: 503 data rows in each CSV
- Prepared row counts: 110 company and financial rows after the Symbol join and sector filter
- Curated signals: 22 records across 11 prepared companies

The requested financials path currently returns HTTP 404. The fallback is the
published companion dataset with the same columns and row count; this is also
the fallback implemented in `build_db.py`. Run that script with `DATABASE_URL`
to load the prepared source-of-truth tables into Postgres.
