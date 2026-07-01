#!/usr/bin/env python3
"""
Generate a Power BI Project (PBIP) scaffold for the ACLED dashboard.

Emits the PBIR (enhanced report) + TMDL (semantic model) text format that opens
in Power BI Desktop. Deterministic: same input -> same GUIDs/ids, so re-running
produces a clean diff. Re-run after editing the CONTRACT below.

Output: powerbi/ACLED/  (ACLED.pbip + ACLED.Report/ + ACLED.SemanticModel/)

PREREQS to open (Power BI Desktop, File > Options > Preview features):
  - Power BI Project (.pbip) save option
  - Store reports using enhanced metadata format (PBIR)
  - Store semantic model using TMDL format
Then wire the Athena ODBC DSN name (default "ACLED_Athena") — see powerbi/README.md.
"""
import json, os, shutil, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "ACLED")
NS = uuid.uuid5(uuid.NAMESPACE_URL, "acled-pbip")

def gid(*parts):        # deterministic hex id (GUID) from a key
    return uuid.uuid5(NS, "/".join(parts))
def hexid(*parts):      # 20-char object name (page/visual folder)
    return gid(*parts).hex[:20]
def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
def wjson(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- CONTRACT ----
# Athena gold tables -> (column, pbi_type). int/bigint->int64, double->double.
TABLES = {
    "gold_geography": [("country","string"),("region","string"),("event_type","string"),
        ("event_count","int64"),("total_fatalities","int64"),("avg_fatalities","double")],
    "gold_yearly_trends": [("year","int64"),("month","int64"),("disorder_type","string"),
        ("event_count","int64"),("total_fatalities","int64")],
    "gold_event_types": [("event_type","string"),("sub_event_type","string"),
        ("event_count","int64"),("total_fatalities","int64"),("avg_fatalities_per_event","double")],
    "gold_event_type_year": [("event_type","string"),("disorder_type","string"),("year","int64"),
        ("event_count","int64"),("total_fatalities","int64")],
    "gold_actors": [("actor1","string"),("year","int64"),
        ("event_count","int64"),("total_fatalities","int64"),("civ_targeting_events","int64")],
    "gold_interaction": [("interaction","string"),("year","int64"),
        ("event_count","int64"),("total_fatalities","int64")],
    "gold_civilian_region": [("region","string"),("year","int64"),
        ("event_count","int64"),("civ_targeting_events","int64"),("total_fatalities","int64")],
    "gold_sources": [("region","string"),("source_scale","string"),
        ("event_count","int64"),("total_fatalities","int64")],
    "gold_country_year": [("country","string"),("iso","int64"),("year","int64"),
        ("event_count","int64"),("total_fatalities","int64")],
    "gold_per_capita": [("country","string"),("iso","int64"),("year","int64"),
        ("event_count","int64"),("total_fatalities","int64"),("population","int64"),
        ("events_per_100k","double"),("fatalities_per_100k","double")],
}
SUM_COLS = {"event_count","total_fatalities","civ_targeting_events","population"}

# table -> [(measure name, DAX, formatString)]
MEASURES = {
    "gold_civilian_region": [("Pct Civilian Targeting",
        "DIVIDE(SUM(gold_civilian_region[civ_targeting_events]), SUM(gold_civilian_region[event_count]))","0.0%")],
    "gold_interaction": [("Fatalities per Event",
        "DIVIDE(SUM(gold_interaction[total_fatalities]), SUM(gold_interaction[event_count]))","0.00")],
}

# (page display name, [visual specs]). role keys -> PBIR roles in build_visual().
PAGES = [
 ("Geography & Deaths", [
    {"type":"clusteredBarChart","title":"Top countries by events","table":"gold_geography",
     "category":"country","y":("Sum","event_count"),"sort_y":True},
    {"type":"filledMap","title":"Fatalities by country","table":"gold_geography",
     "location":"country","y":("Sum","total_fatalities")}]),
 ("Trends Over Time", [
    {"type":"lineChart","title":"Events over time by disorder type","table":"gold_yearly_trends",
     "category":"year","series":"disorder_type","y":("Sum","event_count")},
    {"type":"clusteredColumnChart","title":"Seasonality by month","table":"gold_yearly_trends",
     "category":"month","y":("Sum","event_count")}]),
 ("Event Types", [
    {"type":"clusteredBarChart","title":"Deadliest sub-event types","table":"gold_event_types",
     "category":"sub_event_type","y":("Sum","total_fatalities"),"sort_y":True},
    {"type":"lineChart","title":"Protest vs violence over time","table":"gold_event_type_year",
     "category":"year","series":"event_type","y":("Sum","event_count")}]),
 ("Actors", [
    {"type":"clusteredBarChart","title":"Top actors by events","table":"gold_actors",
     "category":"actor1","y":("Sum","event_count"),"sort_y":True},
    {"type":"clusteredBarChart","title":"Bloodiest interaction types","table":"gold_interaction",
     "category":"interaction","y":("Sum","total_fatalities"),"sort_y":True}]),
 ("Civilian Targeting", [
    {"type":"clusteredBarChart","title":"% civilian targeting by region","table":"gold_civilian_region",
     "category":"region","measure":"Pct Civilian Targeting","sort_measure":True},
    {"type":"lineChart","title":"% civilian targeting over time","table":"gold_civilian_region",
     "category":"year","series":"region","measure":"Pct Civilian Targeting"}]),
 ("Sources & Escalation", [
    {"type":"clusteredColumnChart","title":"Source scale by region","table":"gold_sources",
     "category":"region","series":"source_scale","y":("Sum","event_count")},
    {"type":"scatterChart","title":"Events vs fatalities (country-year)","table":"gold_country_year",
     "x":("Sum","event_count"),"y":("Sum","total_fatalities"),"details":"country"}]),
 ("Per Capita", [
    {"type":"tableEx","title":"Events & fatalities per 100k","table":"gold_per_capita",
     "columns":["country","events_per_100k","fatalities_per_100k"]},
    {"type":"lineChart","title":"Per-capita trend","table":"gold_per_capita",
     "category":"year","series":"country","y":("Sum","events_per_100k")}]),
]

ATHENA_DSN = "ACLED_Athena"
FUNC_SUM = 0

# ---------------------------------------------------------------- FIELDS ------
def col_field(tbl, col):
    return {"Column":{"Expression":{"SourceRef":{"Entity":tbl}},"Property":col}}
def agg_field(tbl, col, func=FUNC_SUM):
    return {"Aggregation":{"Expression":{"Column":{"Expression":{"SourceRef":{"Entity":tbl}},"Property":col}},"Function":func}}
def measure_field(tbl, name):
    return {"Measure":{"Expression":{"SourceRef":{"Entity":tbl}},"Property":name}}

def proj_col(tbl, col, active=False):
    p = {"field":col_field(tbl,col),"queryRef":f"{tbl}.{col}","nativeQueryRef":col}
    if active: p["active"]=True
    return p
def proj_sum(tbl, col):
    return {"field":agg_field(tbl,col),"queryRef":f"Sum({tbl}.{col})","nativeQueryRef":f"Sum of {col}"}
def proj_measure(tbl, name, active=False):
    p = {"field":measure_field(tbl,name),"queryRef":f"{tbl}.{name}","nativeQueryRef":name}
    if active: p["active"]=True
    return p

# ---------------------------------------------------------------- VISUAL ------
def build_visual(spec, name, position):
    tbl = spec["table"]; qs = {}
    def role(r, proj): qs.setdefault(r, {"projections":[]})["projections"].append(proj)

    if spec["type"] == "tableEx":
        for c in spec["columns"]:
            role("Values", proj_sum(tbl,c) if c in SUM_COLS else proj_col(tbl,c))
    else:
        if "category" in spec: role("Category", proj_col(tbl, spec["category"], active=True))
        if "location" in spec: role("Category", proj_col(tbl, spec["location"], active=True))
        if "details"  in spec: role("Category", proj_col(tbl, spec["details"], active=True))
        if "series"   in spec: role("Series",   proj_col(tbl, spec["series"]))
        if "x" in spec: role("X", proj_sum(tbl, spec["x"][1]))
        if "y" in spec: role("Y", proj_sum(tbl, spec["y"][1]))
        if "measure" in spec: role("Y", proj_measure(tbl, spec["measure"]))

    query = {"queryState": qs}
    # descending sort by the value, for ranked bars
    if spec.get("sort_y") and "y" in spec:
        query["sortDefinition"] = {"sort":[{"field":agg_field(tbl,spec["y"][1]),"direction":"Descending"}],"isDefaultSort":True}
    elif spec.get("sort_measure") and "measure" in spec:
        query["sortDefinition"] = {"sort":[{"field":measure_field(tbl,spec["measure"]),"direction":"Descending"}],"isDefaultSort":True}

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

# two visuals side by side on a 1280x720 canvas
POSITIONS = [
    {"x":24,"y":24,"z":0,"width":612,"height":672,"tabOrder":0},
    {"x":644,"y":24,"z":1,"width":612,"height":672,"tabOrder":1},
]

# ---------------------------------------------------------------- TMDL --------
def tmdl_table(tbl, cols):
    L = [f"table {tbl}", f"\tlineageTag: {gid('t',tbl)}", ""]
    for mname, dax, fmt in MEASURES.get(tbl, []):
        L += [f"\tmeasure '{mname}' = {dax}", f"\t\tformatString: {fmt}",
              f"\t\tlineageTag: {gid('m',tbl,mname)}", ""]
    for col, typ in cols:
        summ = "sum" if col in SUM_COLS else "none"
        fmt = None
        if typ == "int64": fmt = "#,0" if col in SUM_COLS else "0"
        elif typ == "double": fmt = "#,0.00"
        L += [f"\tcolumn {col}", f"\t\tdataType: {typ}"]
        if fmt: L.append(f"\t\tformatString: {fmt}")
        L += [f"\t\tlineageTag: {gid('c',tbl,col)}", f"\t\tsummarizeBy: {summ}",
              f"\t\tsourceColumn: {col}", "", "\t\tannotation SummarizationSetBy = Automatic", ""]
    m = ("let\n"
         f'    Source = AmazonAthena.Databases("{ATHENA_DSN}", null, []),\n'
         '    AwsDataCatalog = Source{[Name="AwsDataCatalog",Kind="Database"]}[Data],\n'
         '    acled_dev = AwsDataCatalog{[Name="acled_dev",Kind="Schema"]}[Data],\n'
         f'    {tbl} = acled_dev{{[Name="{tbl}",Kind="Table"]}}[Data]\n'
         "in\n"
         f"    {tbl}")
    L += [f"\tpartition {tbl} = m", "\t\tmode: import", "\t\tsource =",
          "\n".join("\t\t\t\t"+ln for ln in m.splitlines()), "",
          "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L) + "\n"

# ---------------------------------------------------------------- BUILD -------
def build():
    if os.path.exists(ROOT): shutil.rmtree(ROOT)
    SM = os.path.join(ROOT, "ACLED.SemanticModel")
    RP = os.path.join(ROOT, "ACLED.Report")

    # --- pointers ---
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

    # --- semantic model (TMDL) ---
    order = list(TABLES.keys())
    model = ("model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
             "\tsourceQueryCulture: en-US\n\n"
             f"annotation PBI_QueryOrder = {json.dumps(order)}\n\n"
             + "".join(f"ref table {t}\n" for t in order)
             + "\nref cultureInfo en-US\n")
    write(os.path.join(SM,"definition","model.tmdl"), model)
    write(os.path.join(SM,"definition","database.tmdl"), "database\n\tcompatibilityLevel: 1604\n")
    write(os.path.join(SM,"definition","cultures","en-US.tmdl"), "cultureInfo en-US\n")
    for t,cols in TABLES.items():
        write(os.path.join(SM,"definition","tables",f"{t}.tmdl"), tmdl_table(t,cols))

    # --- report (PBIR) ---
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
    print(f"Generated PBIP at {ROOT}")
    print(f"  {len(TABLES)} tables, {len(PAGES)} pages, {sum(len(v) for _,v in PAGES)} visuals")

# ACLED editorial theme (same palette as docs/powerbi_design_spec.md)
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
