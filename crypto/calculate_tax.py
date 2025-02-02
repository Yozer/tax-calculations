from decimal import Decimal
import binance, coinbase, kraken, bittrex, nexo

exchanges = [binance.calculate_tax, coinbase.calculate_tax, kraken.calculate_tax, bittrex.calculate_tax, nexo.calculate_tax]

przychod_total = Decimal(0)
koszt_total = Decimal(0)
dochod_total = Decimal(0)
fiat_staking_total = Decimal(0)

for exchange in exchanges:
    exchange_name, przychod, koszt, fiat_staking = exchange()
    if exchange_name is None:
        continue

    dochod = (przychod - koszt) if przychod > koszt else Decimal(0)
    print(f"Giełda: {exchange_name}\nPrzychód: {przychod}zł Koszt: {koszt}zł Dochód: {dochod}zł Fiat staking: {fiat_staking}zł")
    przychod_total += przychod
    koszt_total += koszt
    fiat_staking_total += fiat_staking

dochod_total = przychod_total - koszt_total
if dochod_total < 0:
    dochod_total = Decimal(0)
rollover_koszt = Decimal(0) if przychod_total > koszt_total else -(przychod_total - koszt_total)
print()
print("Łącznie")
print(f"Przychód: {przychod_total}zł Koszt: {koszt_total}zł Dochód: {dochod_total}zł Rollover koszt: {rollover_koszt} (dodać poprzedni rok!)")
print(f"Fiat staking: {fiat_staking_total}zł")