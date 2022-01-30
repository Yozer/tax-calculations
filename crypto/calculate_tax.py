from decimal import Decimal
import binance

exchanges = [binance.calculate_tax]

przychod_total = Decimal(0)
koszt_total = Decimal(0)
dochod_total = Decimal(0)
fiat_staking_total = Decimal(0)

for exchange in exchanges:
    exchange_name, przychod, koszt, fiat_staking = exchange()
    dochod = (przychod - koszt) if przychod > koszt else Decimal(0)

    print(f"Giełda: {exchange_name}\nPrzychód: {przychod}zł Koszt: {koszt}zł Dochód: {dochod}zł Fiat staking: {fiat_staking}zł")
    przychod_total += przychod
    koszt_total += koszt
    dochod_total += dochod
    fiat_staking_total += fiat_staking

print()
print("Łącznie")
print(f"Przychód: {przychod_total}zł Koszt: {koszt_total}zł Dochód: {dochod_total}zł Fiat staking: {fiat_staking_total}zł")