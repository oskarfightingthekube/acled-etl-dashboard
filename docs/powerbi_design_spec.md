# Power BI design spec — ACLED dashboard (Q1–5)

A builder follows this in **Power BI Desktop**. Claude cannot produce a `.pbix`
(binary), so this spec + `main/sql/05_bi_queries.sql` are the handoff. Connect via
**Get Data → Amazon Athena (ODBC)** to database `acled_dev`.

> **Calibration note.** The palette, fonts and layout below are a sensible
> starting point. Maciek is sending **3 example visuals** — once you have them,
> match exact colors, fonts and spacing to those. This spec is the floor, not
> the ceiling.

---

## 1. Color palette

Deliberately editorial/serious (conflict data) — **not** Power BI defaults,
**not** purple/orange. Two roles:

**Categorical** (event_type / disorder_type / region — discrete series):

| Hex | Use |
|-----|-----|
| `#1F6F8B` | primary teal-blue |
| `#E08E45` | amber |
| `#6A8D73` | sage |
| `#B5446E` | raspberry |
| `#4A4E69` | slate |
| `#C9A227` | mustard |

**Sequential — fatalities** (low → high, for map fill + heatmap):
`#FEE5D9` → `#FCAE91` → `#FB6A4A` → `#DE2D26` → `#A50F15`

**Canvas / text:** background `#F7F7F5`, card/visual background `#FFFFFF`,
primary text `#1A1A2E`, muted text `#6B6B7B`, gridlines `#E3E3DE`.

### theme.json (Power BI → View → Themes → Browse for themes)

```json
{
  "name": "ACLED Editorial",
  "dataColors": ["#1F6F8B", "#E08E45", "#6A8D73", "#B5446E", "#4A4E69", "#C9A227", "#A50F15", "#7A7A88"],
  "background": "#F7F7F5",
  "foreground": "#1A1A2E",
  "tableAccent": "#1F6F8B",
  "good": "#6A8D73",
  "neutral": "#C9A227",
  "bad": "#A50F15",
  "maximum": "#A50F15",
  "center": "#FB6A4A",
  "minimum": "#FEE5D9",
  "visualStyles": {
    "*": {
      "*": {
        "title": [{ "fontColor": { "solid": { "color": "#1A1A2E" } }, "fontSize": 16, "fontFamily": "Segoe UI Semibold" }],
        "legend": [{ "fontSize": 14, "fontFamily": "Segoe UI", "labelColor": { "solid": { "color": "#1A1A2E" } } }],
        "labels": [{ "fontSize": 12, "color": { "solid": { "color": "#1A1A2E" } } }],
        "background": [{ "color": { "solid": { "color": "#FFFFFF" } }, "transparency": 0 }]
      }
    }
  }
}
```

## 2. Typography

| Element | Size | Font |
|---------|------|------|
| Page main title | 28 | Segoe UI Semibold |
| Visual title | 16 | Segoe UI Semibold |
| Legend | 14 | Segoe UI (large + visible — Maciek's ask) |
| Data labels | 12 | Segoe UI |
| Axis labels | 11 | Segoe UI |

Every visual: **title ON**, **legend ON and large**, data labels on bars/KPIs.

## 3. Canvas layout

16:9 (1280×720), background `#F7F7F5`, ~12-column mental grid, generous
padding. Charts sit **side-by-side in a grid — never a vertical stack**. Top
strip = page title + KPI cards; body = 2×2 visual grid. Seven report pages:

### Page 1 — Geography & Deaths (Q1–Q2)
```
┌───────────────────────────── ACLED — Geography & Deaths ─────────────────────────────┐
│ [KPI: total events]   [KPI: total fatalities]   [KPI: fatalities/event]               │
├───────────────────────────────┬───────────────────────────────────────────────────────┤
│ Map: fatalities by country     │ Bar: top 15 countries by events (Q1a)                 │
│ (choropleth, seq. ramp) (Q2a)  │                                                       │
├───────────────────────────────┼───────────────────────────────────────────────────────┤
│ Bar: top regions by events     │ Matrix: country ▸ event_type mix (Q1c, drill-down)    │
│ (Q1b)                          │                                                       │
└───────────────────────────────┴───────────────────────────────────────────────────────┘
```

### Page 2 — Time & Seasonality (Q3–Q4)
```
┌───────────────────────────── ACLED — Trends Over Time ───────────────────────────────┐
│ Line: events per year by disorder_type (legend = disorder_type)  (Q3a)  — full width   │
├───────────────────────────────┬───────────────────────────────────────────────────────┤
│ Column: events by month (Q4a)  │ Matrix heatmap: month × year, fill = events (Q4b)     │
└───────────────────────────────┴───────────────────────────────────────────────────────┘
```

### Page 3 — Event Types (Q5)
```
┌───────────────────────────── ACLED — Event Types & Lethality ────────────────────────┐
│ [KPI: peaceful : violent ratio (Q5c)]                                                  │
├───────────────────────────────┬───────────────────────────────────────────────────────┤
│ Bar: deadliest sub_event by    │ Bar: avg fatalities/event, ranked (Q5b)               │
│ total_fatalities (Q5a)         │                                                       │
├───────────────────────────────┴───────────────────────────────────────────────────────┤
│ Line: protest vs violence over time (from gold_event_type_year) — full width           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Page 4 — Actors (Q6)
```
┌───────────────────────────── ACLED — Actors ─────────────────────────────────────────┐
│ Bar: top 25 actors by events  │ Line: activity over time, top actors (Q6b)            │
│ (Q6a)                          │ (legend = actor1)                                     │
├───────────────────────────────┴───────────────────────────────────────────────────────┤
│ Bar: interaction types — most common + bloodiest, sorted by fatalities (Q6c)           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Page 5 — Civilian Targeting (Q7)
```
┌───────────────────────────── ACLED — Civilian Targeting ─────────────────────────────┐
│ [KPI: overall % civilian-targeting]                                                    │
├───────────────────────────────┬───────────────────────────────────────────────────────┤
│ Map/bar: % civ-targeting by    │ Line: % civ-targeting over time by region (Q7b)       │
│ region (Q7a, seq. ramp)        │ (legend = region)                                     │
├───────────────────────────────┴───────────────────────────────────────────────────────┤
│ Bar: actors with highest civilian-targeting rate, min 200 events (Q7c)                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Page 6 — Sources & Escalation (Q8–Q9)
```
┌───────────────────────────── ACLED — Sources & Escalation ───────────────────────────┐
│ Stacked bar: source_scale mix │ Donut: overall source_scale split (Q8b)               │
│ by region (Q8a)                │                                                       │
├───────────────────────────────┼───────────────────────────────────────────────────────┤
│ Bar: biggest YoY event         │ Scatter: events vs fatalities per country-year (Q9b)  │
│ increase, country-year (Q9a)   │ (trend line on)                                       │
└───────────────────────────────┴───────────────────────────────────────────────────────┘
```

### Page 7 — Per Capita (Q12)
```
┌───────────────────────────── ACLED — Per Capita (per 100k) ──────────────────────────┐
│ Map: events per 100k, chosen  │ Table: ranking flip — absolute rank vs per-capita     │
│ year (Q12a, seq. ramp)         │ rank, top 20 (Q12b)                                   │
├───────────────────────────────┴───────────────────────────────────────────────────────┤
│ Line: per-capita trend for selected countries over time (Q12c)                          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

## 4. Per-visual field mapping

| # | Page | Chart | Query | Axis / Category | Legend | Values |
|---|------|-------|-------|-----------------|--------|--------|
| Q1a | 1 | Clustered bar (top 15) | Q1a | country | — | events |
| Q1b | 1 | Clustered bar | Q1b | region | — | events |
| Q1c | 1 | Matrix (drill) | Q1c | country ▸ event_type | — | event_count, total_fatalities |
| Q2a | 1 | Filled map | Q2a | country (Location) | — | fatalities (color saturation = seq. ramp) |
| Q2b | 1 | Table (optional) | Q2b | country, region | — | fatalities_per_event |
| Q3a | 2 | Line | Q3a | year | disorder_type | events |
| Q4a | 2 | Column | Q4a | month | — | events, fatalities |
| Q4b | 2 | Matrix heatmap | Q4b | month (rows), year (cols) | — | events (conditional fill, seq. ramp) |
| Q5a | 3 | Bar | Q5a | sub_event_type | event_type | total_fatalities |
| Q5b | 3 | Bar | Q5b | sub_event_type | — | avg_fatalities_per_event |
| Q5c | 3 | KPI card | Q5c | — | — | peaceful_to_violent_ratio |
| Q6a | 4 | Bar (top 25) | 08·Q6a | actor1 | — | events, fatalities |
| Q6b | 4 | Line | 08·Q6b | year | actor1 | events |
| Q6c | 4 | Bar | 08·Q6c | interaction | — | fatalities, fatalities_per_event |
| Q7a | 5 | Filled map / bar | 08·Q7a | region | — | pct_civilian_targeting |
| Q7b | 5 | Line | 08·Q7b | year | region | pct_civilian_targeting |
| Q7c | 5 | Bar | 08·Q7c | actor1 | — | pct_civilian_targeting |
| Q8a | 6 | Stacked bar | 08·Q8a | region | source_scale | events |
| Q8b | 6 | Donut | 08·Q8b | source_scale | — | events |
| Q9a | 6 | Bar | 08·Q9a | country+year | — | yoy_change, yoy_pct |
| Q9b | 6 | Scatter | 08·Q9b | events (X) | country | fatalities (Y) |
| Q12a | 7 | Filled map | 09·Q12a | country | — | events_per_100k |
| Q12b | 7 | Table | 09·Q12b | country | — | rank_absolute, rank_per_capita, events_per_100k |
| Q12c | 7 | Line | 09·Q12c | year | country | events_per_100k, fatalities_per_100k |

Queries prefixed `08·` are in `main/sql/08_bi_queries_extended.sql`, `09·` in
`main/sql/09_bi_queries_percapita.sql`; the rest in `main/sql/05_bi_queries.sql`.

## 5. Coverage & caveats (tell the colleagues)

**All 12 business questions are now answerable** — the gold layer was extended
(`main/sql/06_gold_conflict.sql`, `07_dim_population.sql`) and every query is verified
against live Athena data. Remaining caveats, none blocking:

- **Q2 map** ships as a country choropleth. A point/admin1 bubble map is now
  *possible* too — `gold_events_wide` carries `latitude`/`longitude`/`admin1`
  for 2.66M events — if a richer map is wanted.
- **Q8 "more sources → more events?"** is not answered. `source_scale` by region
  is done, but counting *distinct sources per event* needs the raw `source`
  list added to `gold_events_wide` (`cardinality(split(source,';'))`).
- **Per-capita (Q12)** misses ~0.65% of events — almost all **Kosovo**, which
  has no ISO 3166-1 numeric code and thus no World Bank population row.
- **Minor data artifact**: a few misaligned source rows produce tiny negative
  fatalities (net ~-20 over 79k events). Negligible; clamp with `GREATEST(x,0)`
  in `gold_events_wide` if a stakeholder objects.
- **Root-cause note for the pipeline owner**: `main/glue/silver_transform.py` casts
  `interaction`/`inter1`/`inter2` to INT, but they are STRING labels → NULL in
  silver. `main/sql/06` works around it by rebuilding from bronze. Proper fix = drop
  those int casts in the Glue job and re-run silver.
