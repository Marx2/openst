# obligacje.pl selectors (D80 fixtures, captured 2026-09-19)

Fixtures:
- `obligacje_bond_profile_BST0327.html` — bond detail page
  (`https://obligacje.pl/pl/obligacja/BST0327`)
- `obligacje_bond_catalogue_page1.html` —
  listed-bond search page (`.../pl/narzedzia/wyszukiwarka-obligacji-notowanych`)

## Bond detail page (`/pl/obligacja/{SYMBOL}`)

Profile table: `table.table-9` inside `.search-content-box-1` — two-column
`<tr><th>LABEL:</th><td>value</td></tr>` rows. Field → label mapping:

| Field          | `<th>` label              | Sample value (BST0327) |
|----------------|---------------------------|------------------------|
| issuer         | `Emitent:`                | `Best S.A.` (link `.nazwa-emitenta`) |
| series         | `Seria:`                  | `W3` |
| isin           | `ISIN:`                   | `PLBEST000333` |
| market         | `Rynek:`                  | `GPW RR` |
| status         | `Status:`                 | `Notowane` |
| nominal        | `Wartość nominalna:`      | `100.00 PLN` (space thousands sep, 2dp, ISO code suffix) |
| secured        | `Zabezpieczenie:`         | `NIE` / `TAK` |
| coupon_type    | `Typ oprocentowania:`     | `zmienne WIBOR 3M +  4%` |
| current_rate   | `Oprocentowanie bieżące:` | `7.83%` |
| maturity       | `Dzień wykupu` (h4 under `Ważne daty`, h3 block `.note-content`) | `2027-03-07` (ISO, single `<li>`) |

Maturity block: `Ważne daty` h3 → `.note-content` → `h4:Dzień wykupu` →
following `.txt ul li` (first/only `<li>` is the redemption date).
Other h4 blocks: `Pierwsze dni okresów odsetkowych`, `Dni ustalenia prawa do
odsetek`, `Dni wypłaty odsetek`.

There is **no margin column on the detail page** for variable-rate bonds —
the margin is embedded in the coupon-type text (`WIBOR 3M +  4%`). The
catalogue page exposes it as a dedicated column.

## Catalogue page (`/pl/narzedzia/wyszukiwarka-obligacji-notowanych`)

- **Single page — no server-side pagination.** The whole listed-bond universe
  is rendered into `table#tabela` (server default filter: non-archived,
  "wszystkie" selectors). Client-side DataTables 1.13.3 does paging
  (`lengthMenu [50,25,10,-1]`). No `table_info`/pagination links in the HTML;
  scrape the full `<tbody>` of `#tabela` once.
- Row: `<tr><td>...</td>×7</tr>` inside `#tabela tbody`. Columns:
  0. Emitent — `<a href="/pl/emitent/{slug}">{name}</a>`
  1. Kod obligacji — `<a href="/pl/obligacja/{SYMBOL}">{SYMBOL}</a>`
  2. Termin wykupu — ISO date `2028-02-04` (plain text)
  3. Rodzaj oprocentowania — e.g. `zmienne WIBOR 6M` (plain text)
  4. Marża/kupon (pkt. proc.) — `4.8` (plain number; dot decimal)
  5. Aktualny kupon — `8.64%`
  6. Rentowność — calculator link, ignore
- Symbols are plain (no `.WA` suffix, no `-K`-less variants); special
  characters allowed: `BOS0735-K`, `MBK01PERP-K`, `PEO0435-K`, `PKO1034-K`.
- Count at capture: **937 rows, 937 unique symbols** (no duplicates). 5 codes
  carry a hyphen suffix: `BOS0735-K`, `MBK01PERP-K`, `PEO0435-K`, `PKO0935-K`,
  `PKO1034-K`. Note: any `[A-Z0-9.]+`-style symbol regex will undercount (misses
  the hyphenated codes) — match with a character set that includes `-`.
