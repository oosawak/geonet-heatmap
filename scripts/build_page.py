#!/usr/bin/env python3
"""Build the region pages from the Markdown master records.

Each snapshots*/<date>.md holds one day's result (meta lines, station
table, earthquake list, intensity points). The pages embed all snapshots
of their region and offer a date selector (history). Coastline comes
from the region's prefecture polygons in work/japan_pref.geojson.

Regions:
  tohoku -> index.html          (snapshots/)
  nankai -> nankai/index.html   (snapshots-nankai/)  三重・四国とその周辺
"""
import os, re, json, glob, math

ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
REGIONS = {
    "tohoku": {
        "snap_dir": "snapshots", "out": "index.html",
        "prefs": {"青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"},
        "ext": {"latMin": 36.8, "latMax": 41.5, "lonMin": 139.3, "lonMax": 142.3},
        "title": "地殻変動ヒートマップ（試作）― 東北の電子基準点",
        "label": "東北", "other_href": "./nankai/", "other_label": "三重・四国とその周辺",
        "map_long_px": 1600,
        "expl_note": "2011年の東北地方太平洋沖地震の余効変動やプレート運動そのものも含む動きで、観測には数mm程度の誤差があります。",
    },
    "nankai": {
        "snap_dir": "snapshots-nankai", "out": "nankai/index.html",
        "prefs": {"三重県", "徳島県", "香川県", "愛媛県", "高知県",
                  "和歌山県", "奈良県", "滋賀県", "岐阜県", "愛知県", "静岡県",
                  "兵庫県", "大阪府", "京都府", "岡山県", "広島県", "山口県",
                  "大分県", "宮崎県"},
        "ext": {"latMin": 31.3, "latMax": 36.55, "lonMin": 130.6, "lonMax": 139.3},
        "title": "地殻変動ヒートマップ（試作）― 三重・四国とその周辺",
        "pref_labels": True,
        "label": "三重・四国とその周辺", "other_href": "../", "other_label": "東北",
        "map_long_px": 1600,
        "expl_note": "フィリピン海プレートの沈み込みに伴う地殻変動やプレート運動そのものを含む動きで、観測には数mm程度の誤差があります。",
    },
}

def map_size(cfg):
    """Canvas size whose width/height matches the true ground aspect:
    longitude degrees shrink by cos(centre latitude), so
    width/height = lon_range * cos(centre_lat) / lat_range.
    The longer side becomes cfg['map_long_px']."""
    ext = cfg["ext"]
    lat_range = ext["latMax"] - ext["latMin"]
    lon_range = ext["lonMax"] - ext["lonMin"]
    centre = math.radians((ext["latMin"] + ext["latMax"]) / 2.0)
    aspect = lon_range * math.cos(centre) / lat_range
    long_px = cfg["map_long_px"]
    if aspect >= 1:
        return long_px, round(long_px / aspect)
    return round(long_px * aspect), long_px
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

def coastline(prefs):
    gj = os.path.join(ROOT, "work", "japan_pref.geojson")
    data = json.load(open(gj, encoding="utf-8"))
    rings = []
    for feat in data.get("features", []):
        if feat.get("properties", {}).get("nam_ja") not in prefs:
            continue
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for ring in poly:
                rings.append([[round(x, 3), round(y, 3)] for x, y in ring])
    return rings

def pref_labels(prefs):
    """Label point (name without 県/府 suffix, lat, lon) per prefecture:
    the area centroid of its largest outer ring."""
    gj = os.path.join(ROOT, "work", "japan_pref.geojson")
    data = json.load(open(gj, encoding="utf-8"))
    labels = []
    for feat in data.get("features", []):
        name = feat.get("properties", {}).get("nam_ja")
        if name not in prefs:
            continue
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        best = None
        for poly in polys:
            ring = poly[0]
            a = cx = cy = 0.0
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                cross = x1 * y2 - x2 * y1
                a += cross
                cx += (x1 + x2) * cross
                cy += (y1 + y2) * cross
            if a == 0:
                continue
            a *= 0.5
            if best is None or abs(a) > abs(best[0]):
                best = (a, cx / (6 * a), cy / (6 * a))
        if best:
            short = name[:-1] if name.endswith(("県", "府")) else name
            labels.append({"name": short, "lon": round(best[1], 3), "lat": round(best[2], 3)})
    return labels

def build_region(tpl, key, cfg):
    snaps = [parse_snapshot(p) for p in sorted(glob.glob(os.path.join(ROOT, cfg["snap_dir"], "*.md")))]
    if not snaps:
        print(f"SKIP {key}: no snapshots in {cfg['snap_dir']}")
        return None
    nav = (f'他の地域のヒートマップ： <a href="{cfg["other_href"]}">{cfg["other_label"]}</a>'
           f'　（このページは{cfg["label"]}）')
    html = tpl.replace("/*__DATA__*/",
                       json.dumps({"snaps": snaps, "coast": coastline(cfg["prefs"]),
                                   "labels": pref_labels(cfg["prefs"]) if cfg.get("pref_labels") else [],
                                   "snapDir": cfg["snap_dir"]}, ensure_ascii=False))
    map_w, map_h = map_size(cfg)
    html = html.replace("__PAGE_TITLE__", cfg["title"])
    html = html.replace("__REGION_NAV__", nav)
    html = html.replace("__EXT_JSON__", json.dumps(cfg["ext"]))
    html = html.replace("__MAP_W__", str(map_w))
    html = html.replace("__MAP_H__", str(map_h))
    html = html.replace("__EXPL_NOTE__", cfg["expl_note"])
    out = os.path.join(ROOT, cfg["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", out, f"({len(snaps)} snapshots:", ", ".join(s["date"] for s in snaps),
          f"; map {map_w}x{map_h})")
    return out

def main():
    tpl = open(os.path.join(ROOT, "scripts", "template.html"), encoding="utf-8").read()
    built = [build_region(tpl, k, c) for k, c in REGIONS.items()]
    return 0 if any(built) else 1

if __name__ == "__main__":
    raise SystemExit(main())
