CREATE SCHEMA IF NOT EXISTS openst;

CREATE TABLE IF NOT EXISTS openst.cpi_12m (
    date    DATE PRIMARY KEY,
    value   NUMERIC(8,4) NOT NULL
);

CREATE TABLE IF NOT EXISTS openst.bond_series (
    symbol          TEXT PRIMARY KEY,   -- e.g. EDO0936
    name            TEXT NOT NULL,
    series_code     TEXT NOT NULL,      -- EDO, ROD, OTS, …
    issue_date      DATE NOT NULL,
    maturity_date   DATE NOT NULL,
    term_months     INT NOT NULL,
    rate_rule       TEXT NOT NULL,      -- 'fixed' | 'cpi_12m+margin'
    margin          NUMERIC(6,4) NOT NULL,
    fee_b           NUMERIC(6,2) NOT NULL,
    nominal         NUMERIC(8,2) NOT NULL DEFAULT 100.00
);