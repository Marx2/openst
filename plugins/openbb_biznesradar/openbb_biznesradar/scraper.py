# BiznesRadar.pl HTML scraping — confirmed selectors (sourced from the live
# fixtures captured in tests/fixtures/biznesradar/, see docs/plan.md step 16.1).
#
# Data source: https://www.biznesradar.pl/notowania-historyczne/{SYMBOL}
#   page N (N>=2): /notowania-historyczne/{SYMBOL},{N}   (comma-separated page number)
#   Rows are NEWEST-FIRST. 50 data rows per page.
#
# Main data table ("qTableFull"):
#   <table class="qTableFull">                          -- exactly one per page
#     <tr> <th>...header...</th> </tr>                  -- first <tr> = header row
#     <tr> <td>...</td> ... </tr>                       -- subsequent rows = data
#
# Fund / TFI / FIZ table — 2 columns:
#   header text:  Data | Kurs
#   indices:      [0] Data (DD.MM.YYYY)
#                 [1] Kurs (close; dot decimal separator)
#
# Bond / Catalyst table — 7 columns:
#   header text:  Data | Otwarcie | Max | Min | Zamknięcie | Wolumen | Obrót
#   indices:      [0] Data        (DD.MM.YYYY)
#                 [1] Otwarcie     (open)
#                 [2] Max          (high)
#                 [3] Min          (low)
#                 [4] Zamknięcie   (close)
#                 [5] Wolumen      (volume; plain integer)
#                 [6] Obrót        (turnover; NOT exposed in the output model.
#                                   NOTE: thousands separator is a space, e.g. "6 078")
#
# Date format: DD.MM.YYYY (e.g. "11.09.2026") -> datetime.strptime(d, "%d.%m.%Y").
# Decimal separator: dot (standard float parse).
#
# Pagination footer ("buttons pages"):
#   <div class="buttons pages">
#     <span class="pages_pos_current">N</span>               current page (not a link)
#     <a class="pages_pos" href="/notowania-historyczne/{SYMBOL},{N}">N</a>
#     <span class="pages_pos dots">...</span>                ellipsis, ignore
#     <a class="pages_right" href="/notowania-historyczne/{SYMBOL},{N+1}"
#        title="nastepna">...nastepna...</a>                 next-page link
#   Next page => /notowania-historyczne/{SYMBOL},{N} with N = current page + 1.