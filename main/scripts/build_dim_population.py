"""Buduje dane wymiaru populacji (dim_population) z API World Banku.

Źródło: wskaźnik SP.POP.TOTL (total population), lata 1997-2025, wszystkie
kraje. Wynik: dim_population.tsv (tab-separated, bez nagłówka) do wgrania pod
tabelę external `acled_dev.dim_population` (DDL: main/sql/07_dim_population.sql).

Dlaczego TSV, nie CSV: nazwy World Banku zawierają przecinki ("Korea, Rep."),
a OpenCSVSerde w Athenie wymusiłby typ STRING na wszystkich kolumnach —
tab-delimited + LazySimpleSerDe zachowuje INT/BIGINT potrzebne do joinów.

Klucz: ISO 3166-1 numeric (pycountry) — identyczny z kolumną `iso` w ACLED,
więc join działa bez castów. Odpadają agregaty WB (World, income groups...)
oraz terytoria bez kodu numerycznego (Kosowo/XKX, Wyspy Normandzkie/CHI —
jedyne realne luki per capita, ~0,4% zdarzeń).

Braki wartości: forward-fill ostatniej znanej populacji (nieużywany przy
bieżącym vintage WB — 2024/2025 to prawdziwe estymaty).

Użycie (jednorazowy setup, NIE jest częścią DAG-a — patrz airflow/README.md):
    pip install requests pycountry
    python main/scripts/build_dim_population.py
    aws s3 cp dim_population.tsv s3://mw-acled-gold-dev/dim_population/
    # potem DDL z main/sql/07_dim_population.sql w Athenie
"""
import csv

import pycountry
import requests

WB = "https://api.worldbank.org/v2"
YEARS = list(range(1997, 2026))

data = requests.get(
    f"{WB}/country/all/indicator/SP.POP.TOTL",
    params={"format": "json", "per_page": 20000, "date": f"{YEARS[0]}:{YEARS[-1]}"},
    timeout=60,
).json()[1]
meta = requests.get(f"{WB}/country", params={"format": "json", "per_page": 400}, timeout=60).json()[1]
aggregate_iso3 = {c["id"] for c in meta if c["region"]["value"] == "Aggregates"}


def numeric(iso3):
    c = pycountry.countries.get(alpha_3=iso3)
    return int(c.numeric) if c else None


by_country = {}
unmapped = {}
for r in data:
    iso3 = (r.get("countryiso3code") or "").strip()
    if not iso3:
        continue
    num = numeric(iso3)
    if num is None:
        if iso3 not in aggregate_iso3:
            unmapped[iso3] = r["country"]["value"]
        continue
    d = by_country.setdefault(iso3, {"name": r["country"]["value"], "num": num, "years": {}})
    d["years"][int(r["date"])] = r["value"]

rows = []
for iso3, d in by_country.items():
    last_known = None
    for y in YEARS:
        pop = d["years"].get(y)
        if pop is None and last_known is not None:
            pop = last_known  # forward-fill
        elif pop is not None:
            last_known = pop
        rows.append((d["num"], iso3, d["name"], y, pop))

rows.sort(key=lambda r: (r[1], r[3]))
with open("dim_population.tsv", "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    for num, iso3, name, y, pop in rows:
        w.writerow([num, iso3, name, y, "" if pop is None else int(pop)])

print(f"kraje: {len(by_country)}, wiersze: {len(rows)} ({YEARS[0]}-{YEARS[-1]})")
print(f"bez kodu ISO-numeric (pominięte): {unmapped}")
assert any(r[0] == 804 for r in rows), "brak Ukrainy (804) — coś poszło źle"
