# Finance coverage and rejected-candidate review

The 2026-11-05 run detected Air Busan's earnings event, but held it because
operating margin and debt ratio could not be read. The runtime requested CFS
only. A read-only replay found 2026 H1 CFS status 013, while OFS returned 000.

The reader now tries OFS for the same period only after CFS returns 013.
Only after both return 013 does it try an older completed period. Authentication,
quota, transport, malformed-response and future-receipt failures remain explicit
and do not silently fall back. Rows from different bases are never combined.
The same policy is applied to annual quality history. A missing operating profit
is unknown, rather than a zero-profit observation.

Read-only verification on 2026-11-12, as of 2026-11-05:
- Air Busan 298690, DART corporation 00651901.
- 2026 H1 OFS receipt 20260813001537: YTD revenue 493,041,804,570 KRW,
  operating loss 5,071,965,851 KRW, operating margin -1.03%, debt ratio 1646.66%.
- 2025 annual OFS receipt 20260317000736: operating margin -0.54%, debt ratio 801%.
- Restoring data does not make the company eligible: existing loss/debt gates remain.

`data/rejected_candidates.json` separately stores rejected/held decisions,
original reasons and available evidence, and completed daily-close D+1/D+3/D+5
observations. The reference is the decision-day close, NOT an executable intraday
entry or a recommendation. Weekends are not counted as sessions. A missing
reference close does not receive a substitute or invented return. Missing data
remains explicitly missing. Repeated same-day/code/stage/reason observations do
not create new samples. Original decisions are retained even if a later fix
changes the diagnosis.

The three exclusions on 2026-11-05 were restored retrospectively from:
https://github.com/qkdwoals2452-jpg/morning-stock-bot/actions/runs/41959384335
Their provenance and retrospective recording time are stored. Air Busan's 11/5
close was 1,550 KRW; its third subsequent trading-day close (11/10) was 1,882 KRW,
+21.4194%. This is an exclusion audit, not ORION recommendation performance.

The normal morning history step persists the audit. Excluded observations do
not enter `orion_backtest.json`, recommendation totals, or learned score bonuses.
Review multiple comparable decisions before changing any risk threshold.
