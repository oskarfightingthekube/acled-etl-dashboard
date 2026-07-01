# ACLED Power BI project (PBIP scaffold)

Generated, text-based Power BI project (**PBIR** report + **TMDL** model) that
opens in Power BI Desktop. It is a **starting canvas** — model + measures +
7 pages × 2 visuals wired to the gold tables — meant to be restyled and
extended, not a finished dashboard. Pairs with `../docs/powerbi_design_spec.md`.

Regenerate anytime (deterministic — clean diffs):
```
python3 powerbi/generate_pbip.py
```

## Open it (one-time Power BI Desktop setup)

1. **Enable 3 preview features** — File ▸ Options and settings ▸ Options ▸
   Preview features, tick then restart Desktop (needs a 2024+ build):
   - *Power BI Project (.pbip) save option*
   - *Store reports using enhanced metadata format (PBIR)*
   - *Store semantic model using TMDL format*
2. Open `powerbi/ACLED/ACLED.pbip` (or `ACLED.Report/definition.pbir`).

## Wire the Athena connection

The model imports from Athena via the **Amazon Athena** connector, using the
**ODBC DSN** named `ACLED_Athena` via `Odbc.Query` (see `partition` in each
`.tmdl`) — the exact path already authenticated on the team's machine.

1. Install the **Amazon Athena ODBC driver**.
2. ODBC Data Source Administrator ▸ add a DSN named `ACLED_Athena` with:
   AWS Region `eu-central-1`, S3 output location
   `s3://mw-acled-gold-dev/athena-results/`, Workgroup `primary`, your auth.
3. In Desktop: Refresh. To use a different DSN name, edit `ATHENA_DSN` in
   `generate_pbip.py` and regenerate, or find/replace in the `.tmdl` files.

Catalog path in the M: `AwsDataCatalog` ▸ `acled_dev` ▸ table.

## What's inside

- **Model** (`ACLED.SemanticModel`) — KOMPLETNA warstwa semantyczna na
  schemacie gwiazdy: 7 tabel (fact_events + 6 wymiarów), 6 relacji *:1,
  15 miar DAX (folder "Miary", format stringi), 3 hierarchie (Kalendarz,
  Geografia, Typ zdarzenia), chronologiczny sort miesięcy, ukryte klucze
  techniczne, dim_date oznaczona jako tabela dat. Źródło: Odbc.Query po DSN
  `ACLED_Athena` (ta sama ścieżka co ręczne połączenie), tryb Import.
- **Report** (`ACLED.Report`): 7 pages (Geography & Deaths, Trends, Event Types,
  Actors, Civilian Targeting, Sources & Escalation, Per Capita), 2 visuals each,
  bound to the model. Palette applied via the registered `ACLED_Editorial.json`
  theme.

## Caveats (it's a scaffold)

- **Restyle expected.** Positions are a plain 2-up grid; Maciek's styling
  (big legends, titles, layout) goes on top. Calibrate to the 3 reference visuals.
- **`filledMap` / `scatterChart`** may need a field dragged to the right well
  (Location / X-Y) after first open — Power BI loads the rest regardless.
- **If the report won't open due to the theme**, delete the `customTheme` block
  (and the `RegisteredResources` package) from
  `ACLED.Report/definition/report.json`, then import
  `StaticResources/RegisteredResources/ACLED_Editorial.json` manually via
  View ▸ Themes ▸ Browse for themes.
- Save hand-edits as **UTF-8 without BOM**; keep the folder path short (Windows
  260-char limit).
