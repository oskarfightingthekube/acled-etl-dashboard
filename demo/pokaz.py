#!/usr/bin/env python3
"""Live-licznik hurtowni na demo ETL (terminal, pelny ekran na rzutnik).

    python3 demo/pokaz.py            # watch: odpytuje Athene co 20 s
    python3 demo/pokaz.py --raz      # pojedynczy odczyt i wyjscie

Scenariusz: odpal PRZED triggerem DAG-a -> widac stan bazowy. Po zakonczeniu
ETL licznik skacze, pojawia sie zielona delta i swieze zdarzenia na liscie.
Wymaga: aws creds (profil default), pip: rich, pyfiglet.
"""
import sys
import time

import boto3
import pyfiglet
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

REGION = "eu-central-1"
DB = "acled_dev"
OUT = "s3://mw-acled-gold-dev/athena-results/"
POLL_S = 20

athena = boto3.client("athena", region_name=REGION)


def query(sql):
    qid = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DB},
        ResultConfiguration={"OutputLocation": OUT},
        WorkGroup="primary",
    )["QueryExecutionId"]
    while True:
        st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
        if st == "SUCCEEDED":
            break
        if st in ("FAILED", "CANCELLED"):
            raise RuntimeError(st)
        time.sleep(1)
    rows = athena.get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"][1:]
    return [[c.get("VarCharValue", "") for c in r["Data"]] for r in rows]


def snapshot():
    stats = query("SELECT count(*), sum(fatalities), max(event_date) FROM acled_dev.gold_events_wide")[0]
    newest = query(
        "SELECT event_date, country, event_type, fatalities FROM acled_dev.gold_events_wide "
        "ORDER BY event_date DESC, event_id_cnty DESC LIMIT 6"
    )
    return int(stats[0]), int(stats[1]), stats[2], newest


def render(count, fatal, newest_date, newest, baseline, ts):
    big = pyfiglet.figlet_format(f"{count:,}".replace(",", " "), font="big").rstrip("\n")
    delta = count - baseline
    if delta > 0:
        delta_txt = Text(f"▲ +{delta:,} NOWYCH ZDARZEŃ OD STARTU DEMA".replace(",", " "),
                         style="bold black on green3")
    elif delta < 0:
        delta_txt = Text(f"▼ {delta:,}".replace(",", " "), style="bold white on red")
    else:
        delta_txt = Text("— stan bazowy, czekam na ETL —", style="dim")

    head = Panel(
        Group(
            Align.center(Text(big, style="bold cyan")),
            Align.center(Text("ZDARZEŃ W HURTOWNI (fakt gwiazdy)", style="bold")),
            Align.center(delta_txt),
        ),
        border_style="cyan",
    )

    t = Table(expand=True, border_style="grey50",
              title=f"najświeższe zdarzenia (max data: {newest_date})")
    for col, w in (("data", 12), ("kraj", 22), ("typ zdarzenia", 30), ("ofiary", 8)):
        t.add_column(col, width=w)
    for r in newest:
        t.add_row(*r)

    foot = Group(
        Text(" SQL (Athena, co 20 s):  SELECT count(*), sum(fatalities), max(event_date) FROM acled_dev.gold_events_wide", style="dim"),
        Text("                         SELECT event_date, country, event_type, fatalities FROM ... ORDER BY event_date DESC LIMIT 6", style="dim"),
        Text(f" suma ofiar: {fatal:,}".replace(",", " ")
             + f"   ·   odświeżono: {ts}   ·   ACLED · bronze→silver→gold→gwiazda · Airflow",
             style="dim"),
    )
    layout = Layout()
    layout.split_column(Layout(head, size=13), Layout(t), Layout(foot, size=3))
    return layout


def main():
    console = Console()
    count, fatal, nd, newest = snapshot()
    baseline = count
    ts = time.strftime("%H:%M:%S")
    if "--raz" in sys.argv:
        console.print(render(count, fatal, nd, newest, baseline, ts))
        return
    with Live(render(count, fatal, nd, newest, baseline, ts),
              console=console, screen=True, refresh_per_second=4) as live:
        while True:
            time.sleep(POLL_S)
            try:
                count, fatal, nd, newest = snapshot()
                ts = time.strftime("%H:%M:%S")
            except Exception:
                ts = time.strftime("%H:%M:%S") + " (błąd odpytania — pokazuję ostatni stan)"
            live.update(render(count, fatal, nd, newest, baseline, ts))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
