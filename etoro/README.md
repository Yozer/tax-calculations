# eToro Taxes

## How to run
```
cd etoro
python.exe calculate_tax.py
```
Drop `statement_2025.xlsx` in the etoro folder.

## eToro's PIT is wrong (taxreport.pdf)

eToro uses **one** NBP rate per position — the sell date rate — for both przychód AND koszty. wtf?
That's not how Polish tax law works. You convert each amount at the rate from the day before that amount happened (art. 11a ust. 1 ustawy o PIT). Buy amount → buy date rate. Sell amount → sell date rate.


| What | Us | eToro | Who's right |
|---|---|---|---|
| FX rate for przychód | NBP T-1 at **sell date** | NBP T-1 at **sell date** | same, they got one right |
| FX rate for koszty | NBP T-1 at **buy date** | NBP T-1 at **sell date** (!) | **us** — art. 11a ust. 1 PIT |
| CFD amounts | net equity_change at close date | leveraged notional (Amount × Leverage) | **us** — CFD is a derivative, the only cash flow is the settlement P&L. Margin is collateral, not koszt nabycia (art. 17 ust. 1 pkt 10 PIT) |
| CFD shorts | same as longs — net settlement | open = przychód, close = koszty | **us** — no real buy/sell happens, it's opening/closing a contract |
| Commission / Withdrawal Conv Fee | in koszty | lol they just drop it | **us** — it's a real cost, art. 22 ust. 1 |
| Overnight refunds | separate from position P&L | baked into Profit column | **us** — separate dates = better PLN conversion |
