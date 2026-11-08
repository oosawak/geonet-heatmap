#!/usr/bin/env python3
"""Build index.html (repo root, which GitHub Pages publishes) from the
Markdown master records in snapshots/.

Each snapshots/<date>.md holds one day's result (meta lines, station
table, earthquake list, intensity points). The page embeds all snapshots
and offers a date selector (history). Coastline comes from the Tohoku
prefecture polygons in work/japan_pref.geojson.
"""
import os, re, json, glob

ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
EXT = dict(lat_min=36.8, lat_max=41.5, lon_min=139.3, lon_max=142.3)
TOHOKU = {"青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

def table_rows(section_text):
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows

def sections(text):
    out, cur, buf = {}, "_head", []
    for line in text.splitlines():
        if line.startswith("## "):
            out[cur] = "\n".join(buf); cur = line[3:].strip(); buf = []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf)
    return out

def parse_snapshot(path):
    text = open(path, encoding="utf-8").read()
    sec = sections(text)
    meta = {}
    for line in sec.get("_head", "").splitlines():
        line = line.strip()
        if line.startswith("- ") and ": " in line:
            k, v = line[2:].split(": ", 1)
            meta[k.strip()] = v.strip()
    date = meta.get("データ最新日") or os.path.basename(path)[:-3]
    def period(key):
        return DATE_RE.findall(meta.get(key, ""))[:2]
    stations = []
    for r in table_rows(sec.get("観測点ごとの変位", ""))[1:]:
        try:
            stations.append({"code": r[0], "name": r[1], "pref": r[2],
                             "lat": float(r[3]), "lon": float(r[4]),
                             "dE": float(r[5]), "dN": float(r[6]),
                             "h": float(r[7]), "dir": r[8], "v": float(r[9])})
        except (ValueError, IndexError):
            continue
    quakes = []
    for r in table_rows(sec.get("震央リスト（気象庁）", ""))[1:]:
        try:
            quakes.append({"time": r[0], "name": r[1], "lat": float(r[2]),
                           "lon": float(r[3]), "depth": float(r[4]),
                           "mag": float(r[5]), "maxint": r[6], "src": r[7]})
        except (ValueError, IndexError):
            continue
    intensity = []
    for r in table_rows(sec.get("震度観測点（期間最大震度、震度3以上）", ""))[1:]:
        try:
            intensity.append({"name": r[0], "city": r[1], "pref": r[2],
                              "lat": float(r[3]), "lon": float(r[4]),
                              "maxint": r[5], "count": int(r[6])})
        except (ValueError, IndexError):
            continue
    return {"date": date, "sol": meta.get("解", ""),
            "periodA": period("直近期間"), "periodB": period("比較期間"),
            "n": meta.get("観測点数", ""), "nex": (meta.get("除外点数", "").split("（")[0]).strip(),
            "median": meta.get("水平変位の中央値", ""), "max": meta.get("水平変位の最大", ""),
            "quakeNote": meta.get("地震データ", ""), "catRange": meta.get("正式カタログ収録範囲", ""),
            "intNote": meta.get("震度データ", ""), "kpNote": meta.get("地磁気", ""),
            "stations": stations, "quakes": quakes, "intensity": intensity}

def coastline():
    gj = os.path.join(ROOT, "work", "japan_pref.geojson")
    data = json.load(open(gj, encoding="utf-8"))
    rings = []
    for feat in data.get("features", []):
        if feat.get("properties", {}).get("nam_ja") not in TOHOKU:
            continue
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for ring in poly:
                rings.append([[round(x, 3), round(y, 3)] for x, y in ring])
    return rings

def main():
    snaps = [parse_snapshot(p) for p in sorted(glob.glob(os.path.join(ROOT, "snapshots", "*.md")))]
    if not snaps:
        print("ERROR: no snapshots"); return 1
    tpl = open(os.path.join(ROOT, "scripts", "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DATA__*/",
                       json.dumps({"snaps": snaps, "coast": coastline()}, ensure_ascii=False))
    out = os.path.join(ROOT, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", out, f"({len(snaps)} snapshots:", ", ".join(s["date"] for s in snaps), ")")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
