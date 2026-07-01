# Finishing the ACLED dashboard — exact steps

State: SQL + gold layer are **done and live in Athena**. The Power BI project
(`powerbi/ACLED`) is generated. What's left is opening it in Power BI Desktop,
connecting it to Athena, and restyling. Power BI Desktop is **Windows-only** —
Part A solves that for a Mac user.

Known values you'll need throughout:

| Thing | Value |
|---|---|
| AWS account | `613025569184` |
| Region | `eu-central-1` |
| Athena database | `acled_dev` |
| Athena workgroup | `primary` |
| Athena results S3 | `s3://mw-acled-gold-dev/athena-results/` |
| ODBC DSN name (expected by the model) | `ACLED_Athena` |
| Project file to open | `powerbi/ACLED/ACLED.pbip` |

---

## Part 0 — Rotate the leaked IAM key (do first, security)

The old access key was pasted into a chat. Kill it.

1. AWS Console → **IAM** → **Users** → `pjatkowy-oskarek-777` → **Security credentials**.
2. Under *Access keys*, find `AKIAY5OZL3GQMLURCO35` → **Actions → Deactivate**, then **Delete**.
3. **Create access key** → *Application running outside AWS* → create → **copy the new Access key ID + Secret** (you'll paste them into the ODBC DSN in Part C). Store them in a password manager, not a chat.

---

## Part A — Get a Windows environment (Mac can't run Power BI Desktop)

Pick one:

- **A1. A colleague's Windows PC** (simplest — this is Maciek). Merge PR #24, he pulls and opens it. If you truly want to do it yourself, use A2/A3.
- **A2. Parallels Desktop + Windows 11** on your Mac (Apple Silicon runs Windows 11 ARM; Power BI Desktop x64 runs under emulation). ~30 min setup. Install Parallels → install Windows 11 → install Power BI Desktop from the Microsoft Store.
- **A3. Cloud Windows** — Windows 365 Cloud PC, or an Azure/AWS Windows VM. Spin up, RDP in, install Power BI Desktop.

Install **Power BI Desktop** on whichever you pick (Microsoft Store → "Power BI Desktop", free; needs a work/school Microsoft account to sign in, but you can build without publishing).

---

## Part B — Get the files onto the Windows machine

Option 1 — clone the branch directly:
```
git clone -b feat/gold-bi-layer-q1-12 https://github.com/oskarfightingthekube/acled-etl-dashboard.git
```
Option 2 — if the Windows env is a VM sharing your Mac disk, just open the file
from the mounted Mac folder.
Option 3 — after PR #24 is merged into `mac-v:dev`, clone `mac-v/acled-etl-dashboard`.

The project is at `powerbi/ACLED/ACLED.pbip`.

---

## Part C — Install Athena ODBC driver + create the DSN

1. Download **Amazon Athena ODBC driver (v2, 64-bit)** from AWS docs
   ("Connecting to Amazon Athena with ODBC") and install it.
2. Open **ODBC Data Source Administrator (64-bit)** (Start menu → type "ODBC").
3. **System DSN** tab → **Add** → select **Amazon Athena ODBC Driver** → Finish.
4. Fill in **exactly**:
   - **Data Source Name:** `ACLED_Athena`  ← must match, or edit the model later
   - **AWS Region:** `eu-central-1`
   - **S3 Output Location:** `s3://mw-acled-gold-dev/athena-results/`
   - **Workgroup:** `primary`
   - **Catalog:** `AwsDataCatalog`
   - **Authentication Type:** `IAM Credentials`
   - **User (Access Key):** the **new** access key ID from Part 0
   - **Password (Secret Key):** the **new** secret from Part 0
5. **Test** → should say connection successful → **OK**.

> Different DSN name? Either rename here to `ACLED_Athena`, or edit
> `ATHENA_DSN` in `powerbi/generate_pbip.py` and re-run it, or find/replace
> `ACLED_Athena` across `powerbi/ACLED/ACLED.SemanticModel/definition/tables/*.tmdl`.

---

## Part D — Enable the 3 Power BI preview features

Power BI Desktop → **File → Options and settings → Options → Preview features**.
Tick all three, click OK, **restart Power BI Desktop**:

- ☑ **Power BI Project (.pbip) save option**
- ☑ **Store reports using enhanced metadata format (PBIR)**
- ☑ **Store semantic model using TMDL format**

(If a name differs slightly, it's the .pbip / PBIR / TMDL toggle — tick those three.)

---

## Part E — Open the project and load data

1. **File → Open report → Browse** → `powerbi/ACLED/ACLED.pbip` (or double-click it).
2. It opens with the 10 tables in the Data pane and 7 report pages.
3. **Home → Refresh.** First refresh prompts for the connection — pick the
   `ACLED_Athena` DSN / your saved credentials. Data loads from Athena.
   - If it asks about privacy levels, set **Organizational** (or Public) and continue.
   - If refresh errors on one table, check the DSN test in Part C.

---

## Part F — Fix the two visuals that may need a field moved

Most visuals render immediately. Two might show "can't display" until you drag a
field into the right well (Power BI is picky about Location / X-Y roles):

- **Page "Geography & Deaths" → "Fatalities by country" (filled map):** select it,
  in the Visualizations pane put `country` in **Location** and
  `Sum of total_fatalities` in **Color saturation** (or Tooltips).
- **Page "Sources & Escalation" → "Events vs fatalities" (scatter):** put
  `country` in **Values/Details**, `Sum of event_count` on **X Axis**,
  `Sum of total_fatalities` on **Y Axis**.

The fields already exist in the model — you're only assigning wells.

---

## Part G — Apply the theme + restyle (Maciek's style)

- **Theme:** should auto-apply (ACLED_Editorial). If not: **View → Themes →
  Browse for themes** → `powerbi/ACLED/ACLED.Report/StaticResources/RegisteredResources/ACLED_Editorial.json`.
  - If the report refuses to open due to the theme, open
    `powerbi/ACLED/ACLED.Report/definition/report.json` in a text editor,
    delete the `customTheme` block and the `RegisteredResources` package, save,
    reopen, then import the theme via the menu above.
- **Restyle per `docs/powerbi_design_spec.md`** (§2–4): turn legends ON and
  large (14pt), visual titles 16pt Segoe UI Semibold, add a page title textbox,
  arrange side-by-side, add KPI cards. Calibrate colors/fonts to Maciek's 3
  reference visuals.

---

## Part H — Save / share

- **Save** keeps the `.pbip` (text, git-friendly) — commit changes back.
- To share a single file: **File → Save as → .pbix**, or **File → Publish →
  Power BI service** (needs a Power BI Pro/Fabric license + a workspace).

---

## Recap of who does what

- **You (now):** Part 0 (rotate key) — do it regardless.
- **Whoever has Windows (you via Part A, or Maciek):** Parts B–H.
- **Data/SQL:** already finished and live — nothing to redo.
