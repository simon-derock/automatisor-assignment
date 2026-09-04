-- Static company identity and sector classification.
CREATE TABLE IF NOT EXISTS companies (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL CHECK (sector IN ('tech', 'retail', 'manufacturing')),
    sub_industry TEXT,
    headquarters TEXT,
    founded INTEGER
);

-- Point-in-time financial snapshot joined to one company.
CREATE TABLE IF NOT EXISTS financials (
    symbol TEXT PRIMARY KEY REFERENCES companies(symbol) ON DELETE CASCADE,
    price NUMERIC,
    pe_ratio NUMERIC,
    dividend_yield NUMERIC,
    eps NUMERIC,
    week52_low NUMERIC,
    week52_high NUMERIC,
    market_cap NUMERIC,
    ebitda NUMERIC,
    price_to_sales NUMERIC,
    price_to_book NUMERIC,
    source_url TEXT,
    as_of_note TEXT
);

-- Curated qualitative signals used for grounded answers.
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT REFERENCES companies(symbol) ON DELETE CASCADE,
    signal_type TEXT,
    signal_text TEXT NOT NULL,
    source_url TEXT,
    signal_date DATE
);

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
