#!/usr/bin/env python3
"""
Generate a Power BI Project (PBIP) for the ACLED dashboard — STAR SCHEMA model.

The semantic layer is fully code-generated (TMDL): 7 star tables, 6 relation-
ships, DAX measures (with format strings + display folder), hierarchies,
chronological month sort, hidden FK/key columns and dim_date marked as the
date table. Opening this in Power BI Desktop gives a finished semantic model;
only report styling remains.

Data source: Odbc.Query against the ODBC DSN "ACLED_Athena" (the same path
already authenticated on the team's Windows box). Import mode.

Output: powerbi/ACLED/  (ACLED.pbip + ACLED.Report/ + ACLED.SemanticModel/)
Re-run after editing the CONTRACT below — deterministic ids, clean diffs.

Open prereqs (Power BI Desktop, Options > Preview features): PBIP save option,
PBIR enhanced report format, TMDL semantic model format. Extract the WHOLE
repo/zip and open ACLED.pbip in place — .Report/definition/ must exist next
to it (a partial copy of the folders is exactly what breaks with
"Required artifact is missing").
"""
import json, os, shutil, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "ACLED")
NS = uuid.uuid5(uuid.NAMESPACE_URL, "acled-pbip-star")
DSN = "ACLED_Athena"
DB = "acled_dev"

def gid(*parts):
    return uuid.uuid5(NS, "/".join(parts))
def hexid(*parts):
    return gid(*parts).hex[:20]
def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
def wjson(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- CONTRACT ----
# Star tables. hide = columns hidden in report view (FKs/technical keys).
TABLES = {
    "fact_events": {
        "cols": [("event_id_cnty","string"),("iso","int64"),("event_date","dateTime"),
                 ("sub_event_type","string"),("actor1","string"),("source_scale","string"),
                 ("iso_year","int64"),("interaction","string"),
                 ("civilian_targeting_flag","int64"),("latitude","double"),
                 ("longitude","double"),("year","int64"),("fatalities","int64")],
        "hide": ["iso","event_date","sub_event_type","actor1","source_scale",
                 "iso_year","event_id_cnty"],
    },
    "dim_country": {"cols": [("iso","int64"),("country","string"),("region","string")],
                    "hide": ["iso"]},
    "dim_date": {"cols": [("date_key","dateTime"),("year","int64"),("month","int64"),
                          ("month_name","string"),("quarter","int64")],
                 "hide": [], "date_table": True,
                 "sort": {"month_name": "month"}},
    "dim_event_type": {"cols": [("sub_event_type","string"),("event_type","string"),
                                ("disorder_type","string")], "hide": []},
    "dim_actor": {"cols": [("actor","string")], "hide": []},
    "dim_source": {"cols": [("source_scale","string")], "hide": []},
    "dim_population_year": {"cols": [("iso_year","int64"),("iso","int64"),("year","int64"),
                                     ("country_name","string"),("population","int64")],
                            "hide": ["iso_year","iso","year"]},
}
SUM_COLS = {"fatalities","civilian_targeting_flag","population"}

# (from many-side column, to one-side column)
RELATIONSHIPS = [
    ("fact_events.iso",            "dim_country.iso"),
    ("fact_events.event_date",     "dim_date.date_key"),
    ("fact_events.sub_event_type", "dim_event_type.sub_event_type"),
    ("fact_events.actor1",         "dim_actor.actor"),
    ("fact_events.source_scale",   "dim_source.source_scale"),
    ("fact_events.iso_year",       "dim_population_year.iso_year"),
]

# (name, DAX, formatString) — all on fact_events, folder "Miary"
MEASURES = [
    ("Total Events", "COUNTROWS(fact_events)", "#,0"),
    ("Total Fatalities", "SUM(fact_events[fatalities])", "#,0"),
    ("Fatalities per Event", "DIVIDE([Total Fatalities], [Total Events])", "0.00"),
    ("Civilian Targeting Events", "SUM(fact_events[civilian_targeting_flag])", "#,0"),
    ("Pct Civilian Targeting", "DIVIDE([Civilian Targeting Events], [Total Events])", "0.0%"),
    ("Distinct Actors", "DISTINCTCOUNT(fact_events[actor1])", "#,0"),
    ("Distinct Countries", "DISTINCTCOUNT(fact_events[iso])", "#,0"),
    ("Peaceful Protests",
     "CALCULATE([Total Events], dim_event_type[sub_event_type] = \"Peaceful protest\")", "#,0"),
    ("Violent Demonstrations",
     "CALCULATE([Total Events], dim_event_type[sub_event_type] IN {\"Violent demonstration\", "
     "\"Protest with intervention\", \"Excessive force against protesters\"})", "#,0"),
    ("Peaceful to Violent Ratio", "DIVIDE([Peaceful Protests], [Violent Demonstrations])", "0.00"),
    ("Events LY", "CALCULATE([Total Events], DATEADD(dim_date[date_key], -1, YEAR))", "#,0"),
    ("YoY Events %", "DIVIDE([Total Events] - [Events LY], [Events LY])", "0.0%"),
    ("Population", "SUM(dim_population_year[population])", "#,0"),
    ("Events per 100k", "DIVIDE([Total Events] * 100000, [Population])", "0.00"),
    ("Fatalities per 100k", "DIVIDE([Total Fatalities] * 100000, [Population])", "0.00"),
]

# table -> [(hierarchy name, [(level name, column)])]
HIERARCHIES = {
    "dim_date": [("Kalendarz", [("Rok","year"),("Kwartał","quarter"),("Miesiąc","month_name")])],
    "dim_country": [("Geografia", [("Region","region"),("Kraj","country")])],
    "dim_event_type": [("Typ zdarzenia", [("Disorder","disorder_type"),
                                          ("Event","event_type"),("Sub-event","sub_event_type")])],
}

# report pages: visuals bound to dims + measures (semantic style, not rollups)
PAGES = [
 ("Geography & Deaths", [
    {"type":"clusteredBarChart","title":"Top countries by events",
     "category":("dim_country","country"),"y_measure":"Total Events","sort":"measure"},
    {"type":"filledMap","title":"Fatalities by country",
     "category":("dim_country","country"),"y_measure":"Total Fatalities"}]),
 ("Trends Over Time", [
    {"type":"lineChart","title":"Events over time by disorder type",
     "category":("dim_date","year"),"series":("dim_event_type","disorder_type"),
     "y_measure":"Total Events"},
    {"type":"clusteredColumnChart","title":"Seasonality by month",
     "category":("dim_date","month_name"),"y_measure":"Total Events"}]),
 ("Event Types", [
    {"type":"clusteredBarChart","title":"Deadliest sub-event types",
     "category":("dim_event_type","sub_event_type"),"y_measure":"Total Fatalities","sort":"measure"},
    {"type":"lineChart","title":"Protest vs violence over time",
     "category":("dim_date","year"),"series":("dim_event_type","event_type"),
     "y_measure":"Total Events"}]),
 ("Actors", [
    {"type":"clusteredBarChart","title":"Top actors by events",
     "category":("dim_actor","actor"),"y_measure":"Total Events","sort":"measure"},
    {"type":"clusteredBarChart","title":"Bloodiest interaction types",
     "category":("fact_events","interaction"),"y_measure":"Total Fatalities","sort":"measure"}]),
 ("Civilian Targeting", [
    {"type":"clusteredBarChart","title":"% civilian targeting by region",
     "category":("dim_country","region"),"y_measure":"Pct Civilian Targeting","sort":"measure"},
    {"type":"lineChart","title":"% civilian targeting over time",
     "category":("dim_date","year"),"series":("dim_country","region"),
     "y_measure":"Pct Civilian Targeting"}]),
 ("Sources & Escalation", [
    {"type":"clusteredColumnChart","title":"Source scale by region",
     "category":("dim_country","region"),"series":("dim_source","source_scale"),
     "y_measure":"Total Events"},
    {"type":"scatterChart","title":"Events vs fatalities (country-year)",
     "details":("dim_country","country"),"x_measure":"Total Events",
     "y_measure":"Total Fatalities"}]),
 ("Per Capita", [
    {"type":"tableEx","title":"Events & fatalities per 100k",
     "columns":[("dim_country","country")],"measures":["Events per 100k","Fatalities per 100k"]},
    {"type":"lineChart","title":"Per-capita trend",
     "category":("dim_date","year"),"series":("dim_country","country"),
     "y_measure":"Events per 100k"}]),
]

# ---------------------------------------------------------------- PBIR --------
def col_field(tbl, col):
    return {"Column":{"Expression":{"SourceRef":{"Entity":tbl}},"Property":col}}
def measure_field(name, tbl="fact_events"):
    return {"Measure":{"Expression":{"SourceRef":{"Entity":tbl}},"Property":name}}
def proj(field, qref, active=False):
    p = {"field":field,"queryRef":qref,"nativeQueryRef":qref.split(".")[-1]}
    if active: p["active"] = True
    return p

def build_visual(spec, name, position):
    qs = {}
    def role(r, p): qs.setdefault(r, {"projections":[]})["projections"].append(p)

    if spec["type"] == "tableEx":
        for t, c in spec["columns"]:
            role("Values", proj(col_field(t,c), f"{t}.{c}"))
        for m in spec["measures"]:
            role("Values", proj(measure_field(m), f"fact_events.{m}"))
    else:
        if "category" in spec:
            t, c = spec["category"]; role("Category", proj(col_field(t,c), f"{t}.{c}", active=True))
        if "details" in spec:
            t, c = spec["details"]; role("Category", proj(col_field(t,c), f"{t}.{c}", active=True))
        if "series" in spec:
            t, c = spec["series"]; role("Series", proj(col_field(t,c), f"{t}.{c}"))
        if "x_measure" in spec:
            role("X", proj(measure_field(spec["x_measure"]), f"fact_events.{spec['x_measure']}"))
        if "y_measure" in spec:
            role("Y", proj(measure_field(spec["y_measure"]), f"fact_events.{spec['y_measure']}"))

    query = {"queryState": qs}
    if spec.get("sort") == "measure":
        query["sortDefinition"] = {
            "sort":[{"field":measure_field(spec["y_measure"]),"direction":"Descending"}],
            "isDefaultSort":True}

    return {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
        "name":name,
        "position":position,
        "visual":{
            "visualType":spec["type"],
            "query":query,
            "visualContainerObjects":{"title":[{"properties":{"text":{"expr":{"Literal":{"Value":f"'{spec['title']}'"}}}}}]},
            "drillFilterOtherVisuals":True,
        },
    }

POSITIONS = [
    {"x":24,"y":24,"z":0,"width":612,"height":672,"tabOrder":0},
    {"x":644,"y":24,"z":1,"width":612,"height":672,"tabOrder":1},
]

# ---------------------------------------------------------------- TMDL --------
def tmdl_table(tbl, meta):
    L = [f"table {tbl}", f"\tlineageTag: {gid('t',tbl)}"]
    if meta.get("date_table"):
        L.append("\tdataCategory: Time")
    L.append("")

    if tbl == "fact_events":
        for mname, dax, fmt in MEASURES:
            L += [f"\tmeasure '{mname}' = {dax}",
                  f"\t\tformatString: {fmt}",
                  f"\t\tlineageTag: {gid('m',mname)}",
                  "\t\tdisplayFolder: Miary", ""]

    sort = meta.get("sort", {})
    for col, typ in meta["cols"]:
        summ = "sum" if col in SUM_COLS else "none"
        L += [f"\tcolumn {col}", f"\t\tdataType: {typ}"]
        if typ == "int64":
            L.append(f"\t\tformatString: {'#,0' if col in SUM_COLS else '0'}")
        elif typ == "double":
            L.append("\t\tformatString: #,0.00")
        elif typ == "dateTime":
            L += ["\t\tformatString: yyyy-mm-dd"]
        if col in meta["hide"]:
            L.append("\t\tisHidden")
        if col in sort:
            L.append(f"\t\tsortByColumn: {sort[col]}")
        if meta.get("date_table") and col == "date_key":
            L.append("\t\tisKey")
        L += [f"\t\tlineageTag: {gid('c',tbl,col)}",
              f"\t\tsummarizeBy: {summ}",
              f"\t\tsourceColumn: {col}", "",
              "\t\tannotation SummarizationSetBy = Automatic", ""]

    for hname, levels in HIERARCHIES.get(tbl, []):
        L += [f"\thierarchy '{hname}'", f"\t\tlineageTag: {gid('h',tbl,hname)}", ""]
        for lname, lcol in levels:
            L += [f"\t\tlevel '{lname}'",
                  f"\t\t\tlineageTag: {gid('l',tbl,hname,lname)}",
                  f"\t\t\tcolumn: {lcol}", ""]

    m = ("let\n"
         f'    Source = Odbc.Query("dsn={DSN}", "SELECT * FROM {DB}.{tbl}")\n'
         "in\n"
         "    Source")
    L += [f"\tpartition {tbl} = m", "\t\tmode: import", "\t\tsource =",
          "\n".join("\t\t\t\t"+ln for ln in m.splitlines()), "",
          "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L) + "\n"

def tmdl_relationships():
    L = []
    for frm, to in RELATIONSHIPS:
        L += [f"relationship {gid('r',frm,to)}",
              f"\tfromColumn: {frm}",
              f"\ttoColumn: {to}", ""]
    return "\n".join(L) + "\n"

# ---------------------------------------------------------------- BUILD -------
def build():
    if os.path.exists(ROOT): shutil.rmtree(ROOT)
    SM = os.path.join(ROOT, "ACLED.SemanticModel")
    RP = os.path.join(ROOT, "ACLED.Report")

    wjson(os.path.join(ROOT,"ACLED.pbip"), {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version":"1.0","artifacts":[{"report":{"path":"ACLED.Report"}}],
        "settings":{"enableAutoRecovery":True}})
    wjson(os.path.join(RP,"definition.pbir"), {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version":"4.0","datasetReference":{"byPath":{"path":"../ACLED.SemanticModel"}}})
    wjson(os.path.join(SM,"definition.pbism"), {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version":"4.2","settings":{}})

    order = list(TABLES.keys())
    model = ("model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
             "\tsourceQueryCulture: en-US\n\n"
             f"annotation PBI_QueryOrder = {json.dumps(order)}\n\n"
             + "".join(f"ref table {t}\n" for t in order)
             + "\nref cultureInfo en-US\n")
    write(os.path.join(SM,"definition","model.tmdl"), model)
    write(os.path.join(SM,"definition","database.tmdl"), "database\n\tcompatibilityLevel: 1604\n")
    write(os.path.join(SM,"definition","cultures","en-US.tmdl"), "cultureInfo en-US\n")
    write(os.path.join(SM,"definition","relationships.tmdl"), tmdl_relationships())
    for t, meta in TABLES.items():
        write(os.path.join(SM,"definition","tables",f"{t}.tmdl"), tmdl_table(t, meta))

    theme_name = "ACLED_Editorial.json"
    wjson(os.path.join(RP,"StaticResources","RegisteredResources",theme_name), THEME)
    page_names = [hexid("page",dn) for dn,_ in PAGES]
    wjson(os.path.join(RP,"definition","report.json"), {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection":{
            "baseTheme":{"name":"CY24SU10","type":"SharedResources"},
            "customTheme":{"name":theme_name,"type":"RegisteredResources"}},
        "resourcePackages":[
            {"resourcePackage":{"name":"SharedResources","type":"SharedResources","items":[]}},
            {"resourcePackage":{"name":"RegisteredResources","type":"RegisteredResources",
                "items":[{"name":theme_name,"path":theme_name,"type":"Image"}]}}],
        "settings":{"useStylableVisualContainerHeader":True,"defaultDrillFilterOtherVisuals":True},
        "annotations":[{"name":"defaultPage","value":page_names[0]}]})
    wjson(os.path.join(RP,"definition","version.json"), {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version":"2.0.0"})
    wjson(os.path.join(RP,"definition","pages","pages.json"), {
        "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder":page_names,"activePageName":page_names[0]})
    for (dn, visuals), pname in zip(PAGES, page_names):
        pdir = os.path.join(RP,"definition","pages",pname)
        wjson(os.path.join(pdir,"page.json"), {
            "$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name":pname,"displayName":dn,"displayOption":"FitToPage","height":720,"width":1280})
        for i, spec in enumerate(visuals):
            vname = hexid("visual",dn,spec["title"])
            wjson(os.path.join(pdir,"visuals",vname,"visual.json"),
                  build_visual(spec, vname, POSITIONS[i]))

    write(os.path.join(ROOT,".gitignore"), "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    n_meas = len(MEASURES); n_rel = len(RELATIONSHIPS)
    print(f"Generated PBIP at {ROOT}")
    print(f"  {len(TABLES)} tables, {n_rel} relationships, {n_meas} measures, "
          f"{sum(len(h) for h in HIERARCHIES.values())} hierarchies, "
          f"{len(PAGES)} pages, {sum(len(v) for _,v in PAGES)} visuals")

THEME = {
    "name":"ACLED Editorial",
    "dataColors":["#1F6F8B","#E08E45","#6A8D73","#B5446E","#4A4E69","#C9A227","#A50F15","#7A7A88"],
    "background":"#F7F7F5","foreground":"#1A1A2E","tableAccent":"#1F6F8B",
    "good":"#6A8D73","neutral":"#C9A227","bad":"#A50F15",
    "maximum":"#A50F15","center":"#FB6A4A","minimum":"#FEE5D9",
    "visualStyles":{"*":{"*":{
        "title":[{"fontColor":{"solid":{"color":"#1A1A2E"}},"fontSize":16,"fontFamily":"Segoe UI Semibold"}],
        "legend":[{"fontSize":14,"fontFamily":"Segoe UI","labelColor":{"solid":{"color":"#1A1A2E"}}}],
        "labels":[{"fontSize":12,"color":{"solid":{"color":"#1A1A2E"}}}],
        "background":[{"color":{"solid":{"color":"#FFFFFF"}},"transparency":0}]}}},
}

if __name__ == "__main__":
    build()
