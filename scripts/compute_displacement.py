#!/usr/bin/env python3
"""Parse GEONET .pos files and compute per-station displacement:
mean of latest 7 days vs mean of the 7-day window ~30 days earlier.
Also collects the overlay data for the same period (JMA earthquakes,
JMA intensity points, GFZ Kp) and writes everything into the Markdown
master record.

Outputs:
  - snapshots/<latest-date>.md  (Markdown 正本: meta + tables)
  - work/stations_<SOL>.json    (intermediate, for debugging)

Usage:
  python3 scripts/compute_displacement.py [--data-dir data] [--sol F5.1]
"""
import os, re, json, math, glob, argparse, sys
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
REGIONS = {
    "tohoku": {
        "bbox": dict(lat_min=36.8, lat_max=41.5, lon_min=139.3, lon_max=142.3),
        "stations_list": "work/stations_list.json",
        "snap_dir": "snapshots",
        "quake_box": (35.5, 42.5, 138.0, 145.0),  # lat_min, lat_max, lon_min, lon_max
        "intensity_prefs": {"青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"},
        "intensity_codes": {"02", "03", "04", "05", "06", "07"},
        "region_ja": "東北",
    },
    "nankai": {
        "bbox": dict(lat_min=31.3, lat_max=36.55, lon_min=130.6, lon_max=139.3),
        "stations_list": "work/stations_list_nankai.json",
        "snap_dir": "snapshots-nankai",
        "quake_box": (30.5, 37.35, 129.8, 140.1),
        "intensity_prefs": {"三重県", "徳島県", "香川県", "愛媛県", "高知県",
                            "和歌山県", "奈良県", "滋賀県", "岐阜県", "愛知県",
                            "静岡県", "兵庫県", "大阪府", "京都府", "岡山県",
                            "広島県", "山口県", "大分県", "宮崎県"},
        "intensity_codes": {"21", "22", "23", "24", "25", "26", "27", "28", "29",
                            "30", "33", "34", "35", "36", "37", "38", "39",
                            "44", "45"},
        "region_ja": "三重・四国とその周辺",
    },
}
M_PER_DEG = 111194.9  # spherical approx, fine for differencing
SOL_LABEL = {
    "F5.1": "F5.1（最終解・ITRF2020）",
    "F5": "F5（最終解・ITRF2014）",
    "R5.1": "R5.1（速報解・ITRF2020）",
    "R5": "R5（速報解・ITRF2014）",
}
DIRS = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]

def dir8(dE, dN):
    ang = math.degrees(math.atan2(dE, dN)) % 360
    return DIRS[int((ang + 22.5) // 45) % 8]

def parse_pos(path):
    name = None; rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(" J_NAME"):
                name = line.split(None, 1)[1].strip()
            elif re.match(r"^ \d{4} \d{2} \d{2} ", line):
                p = line.split()
                date = dt.date(int(p[0]), int(p[1]), int(p[2]))
                lat, lon, h = float(p[7]), float(p[8]), float(p[9])
                rows.append((date, lat, lon, h))
    return name, rows

def window_mean(rows, end, days=7):
    start = end - dt.timedelta(days=days - 1)
    sel = [r for r in rows if start <= r[0] <= end]
    if len(sel) < 4:
        return None
    n = len(sel)
    return (sum(r[1] for r in sel) / n, sum(r[2] for r in sel) / n,
            sum(r[3] for r in sel) / n, sel[0][0], sel[-1][0], n)

def compute_stations(data_dir, cfg):
    bbox = cfg["bbox"]
    names, prefs = {}, {}
    sl = os.path.join(ROOT, cfg["stations_list"])
    if os.path.exists(sl):
        for c, v in json.load(open(sl, encoding="utf-8")).items():
            names[c], prefs[c] = v[0], v[1]
    fr = os.path.join(ROOT, "work", "fetch_result.json")
    if os.path.exists(fr):
        fetch = json.load(open(fr, encoding="utf-8"))
        for c, v in fetch.get("stations", {}).items():
            names.setdefault(c, v[0]); prefs.setdefault(c, v[1])
    stations, excluded, skipped = [], [], []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.pos"))):
        code = os.path.basename(path).split(".")[0]
        jname, rows = parse_pos(path)
        if not rows:
            skipped.append((code, "no data rows")); continue
        latest = max(r[0] for r in rows)
        a = window_mean(rows, latest)
        b = window_mean(rows, latest - dt.timedelta(days=30))
        if not a or not b:
            skipped.append((code, "window shortage")); continue
        lat0 = sum(r[1] for r in rows) / len(rows)
        lon0 = sum(r[2] for r in rows) / len(rows)
        if not (bbox["lat_min"] <= lat0 <= bbox["lat_max"]
                and bbox["lon_min"] <= lon0 <= bbox["lon_max"]):
            skipped.append((code, "outside bbox")); continue
        dN = (a[0] - b[0]) * M_PER_DEG * 1000.0
        dE = (a[1] - b[1]) * M_PER_DEG * math.cos(math.radians(lat0)) * 1000.0
        vert = (a[2] - b[2]) * 1000.0
        horiz = math.hypot(dE, dN)
        rec = {"code": code, "name": jname or names.get(code, ""), "pref": prefs.get(code, ""),
               "lat": round(lat0, 5), "lon": round(lon0, 5),
               "dE_mm": round(dE, 1), "dN_mm": round(dN, 1),
               "horiz_mm": round(horiz, 1), "vert_mm": round(vert, 1),
               "dir": dir8(dE, dN),
               "winA": [str(a[3]), str(a[4])], "winB": [str(b[3]), str(b[4])],
               "latest": str(latest)}
        if horiz > 50 or abs(vert) > 80:
            rec["reason"] = f"horiz={horiz:.0f}mm vert={vert:.0f}mm (suspected offset)"
            excluded.append(rec)
        else:
            stations.append(rec)
    stations.sort(key=lambda s: -s["horiz_mm"])
    return stations, excluded, skipped

def fetch_extras(winB_start, winA_end, latest, cfg):
    """Quakes (JMA catalog+daily merged), intensity points (JMA info JSON),
    geomagnetic Kp (GFZ). Each guarded: failures yield empty data."""
    extras = {"quakes": [], "cat_through": None, "intensity": [],
              "int_cov": None, "int_period_max": None, "kp": None}
    d0, d1 = dt.date.fromisoformat(winB_start), dt.date.fromisoformat(winA_end)
    try:
        import jma_quakes
        (jma_quakes.QLAT_MIN, jma_quakes.QLAT_MAX,
         jma_quakes.QLON_MIN, jma_quakes.QLON_MAX) = cfg["quake_box"]
        extras["quakes"], extras["cat_through"] = jma_quakes.fetch_merged(d0, d1, 3.0)
    except Exception as ex:
        print("quakes fetch failed:", ex, flush=True)
    try:
        import jma_intensity
        jma_intensity.PREFS = cfg["intensity_prefs"]
        jma_intensity.PREF_CODES = cfg["intensity_codes"]
        pts, cs, ce, pm = jma_intensity.fetch_intensity(d0, d1, 3)
        extras["intensity"] = pts
        extras["int_cov"] = (cs, ce) if cs else None
        extras["int_period_max"] = pm
    except Exception as ex:
        print("intensity fetch failed:", ex, flush=True)
    try:
        import geomag
        extras["kp"] = geomag.kp_for_date(dt.date.fromisoformat(latest))
    except Exception as ex:
        print("geomag fetch failed:", ex, flush=True)
    return extras

def write_snapshot(meta, stations, excluded, extras, cfg):
    label = meta["solution_label"]
    latest = meta["latest_date"]
    a, b = meta["winA"], meta["winB"]
    top = stations[0]
    quakes = extras["quakes"]
    n_fin = sum(1 for q in quakes if q["src"] == "確定")
    qb = cfg["quake_box"]
    L = [
        f"# 地殻変動スナップショット（{latest}、{cfg['region_ja']}）",
        "",
        f"- 解: {label}",
        f"- データ最新日: {latest}",
        f"- 直近期間: {a[0]} 〜 {a[1]}（7日間平均）",
        f"- 比較期間: {b[0]} 〜 {b[1]}（7日間平均、約30日前）",
        f"- 観測点数: {meta['n_stations']}",
        f"- 除外点数: {meta['n_excluded']}（異常に大きな変位、アンテナ交換などによる見かけの跳びの疑い）",
        f"- 水平変位の中央値: {meta['median_mm']:.1f} mm",
        f"- 水平変位の最大: {meta['max_mm']:.1f} mm（{top['name']}・{top['pref']}）",
        f"- 地震データ: 震央 {len(quakes)} 件（確定 {n_fin} 件／暫定 {len(quakes) - n_fin} 件、M3.0以上、緯度{qb[0]}〜{qb[1]}・経度{qb[2]}〜{qb[3]}）",
        "- 正式カタログ収録範囲: " + (f"〜{extras['cat_through']}（これより後は暫定値）"
                                     if extras["cat_through"] else "現時点で対象期間分は未刊行（全件が暫定値）"),
    ]
    if extras["int_cov"]:
        cs, ce = extras["int_cov"]
        L.append(f"- 震度データ: 震度3以上の観測点 {len(extras['intensity'])} 点"
                 f"（集計期間 {cs} 〜 {ce}、地震情報JSONの公開範囲による。"
                 f"期間内の{cfg['region_ja']}の最大震度: {extras['int_period_max'] or '―'}）")
    else:
        L.append("- 震度データ: 取得できず")
    L.append("- 地磁気: " + (f"Kp指数 最大 {extras['kp']:.1f}（GFZ、{latest}）"
                             if extras["kp"] is not None else "取得できず"))
    L += ["", "## 観測点ごとの変位", "",
          "| 観測点コード | 観測点 | 県 | 緯度 | 経度 | 東西変位 (mm) | 南北変位 (mm) | 水平変位 (mm) | 向き | 上下変位 (mm) |",
          "|---|---|---|---:|---:|---:|---:|---:|---|---:|"]
    for s in stations:
        L.append(f"| {s['code']} | {s['name']} | {s['pref']} | {s['lat']:.5f} | {s['lon']:.5f} "
                 f"| {s['dE_mm']:.1f} | {s['dN_mm']:.1f} | {s['horiz_mm']:.1f} | {s['dir']} | {s['vert_mm']:+.1f} |")
    L += ["", "## 除外した観測点", ""]
    if excluded:
        for e in excluded:
            L.append(f"- {e['name']}（{e['pref']}）: {e.get('reason', '')}")
    else:
        L.append("（なし）")
    L += ["", "## 震央リスト（気象庁）", "",
          "震源データ: 気象庁。確定＝地震月報（カタログ編）震源データ、暫定＝日別の震源リスト。",
          "",
          "| 日時 | 震央地名 | 緯度 | 経度 | 深さ (km) | M | 最大震度 | 由来 |",
          "|---|---|---:|---:|---:|---:|---|---|"]
    for q in sorted(quakes, key=lambda q: q["time"], reverse=True):
        L.append(f"| {q['time']} | {q['name']} | {q['lat']:.3f} | {q['lon']:.3f} "
                 f"| {q['depth_km']:.0f} | {q['mag']:.1f} | {q.get('maxint') or '―'} | {q['src']} |")
    L += ["", "## 震度観測点（期間最大震度、震度3以上）", "",
          "震度データ: 気象庁（地震情報JSON）。観測点ごとに集計期間中の最大震度。",
          ""]
    if extras["intensity"]:
        L += ["| 観測点 | 市町村 | 県 | 緯度 | 経度 | 最大震度 | 観測回数 |",
              "|---|---|---|---:|---:|---|---:|"]
        for p in extras["intensity"]:
            L.append(f"| {p['name']} | {p['city']} | {p['pref']} | {p['lat']:.2f} | {p['lon']:.2f} "
                     f"| {p['maxint']} | {p['count']} |")
    else:
        L.append("（震度3以上の観測点なし）")
    L.append("")
    path = os.path.join(ROOT, cfg["snap_dir"], f"{latest}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--sol", default="F5.1")
    ap.add_argument("--region", choices=sorted(REGIONS), default="tohoku")
    ap.add_argument("--no-extras", action="store_true")
    args = ap.parse_args()
    cfg = REGIONS[args.region]
    data_dir = os.path.join(ROOT, args.data_dir)
    label = SOL_LABEL.get(args.sol, args.sol)
    stations, excluded, skipped = compute_stations(data_dir, cfg)
    if not stations:
        print("ERROR: no stations computed"); return 1
    from collections import Counter
    winA = Counter(tuple(s["winA"]) for s in stations).most_common(1)[0][0]
    winB = Counter(tuple(s["winB"]) for s in stations).most_common(1)[0][0]
    latest = max(s["latest"] for s in stations)
    hs = sorted(s["horiz_mm"] for s in stations)
    def pct(q):
        return hs[min(len(hs) - 1, int(q * len(hs)))]
    meta = {"solution": args.sol, "solution_label": label,
            "n_stations": len(stations), "n_excluded": len(excluded),
            "n_skipped": len(skipped),
            "median_mm": hs[len(hs) // 2], "p90_mm": pct(0.90), "p95_mm": pct(0.95),
            "max_mm": hs[-1], "latest_date": latest,
            "winA": list(winA), "winB": list(winB)}
    extras = ({"quakes": [], "cat_through": None, "intensity": [],
               "int_cov": None, "int_period_max": None, "kp": None}
              if args.no_extras else fetch_extras(winB[0], winA[1], latest, cfg))
    path = write_snapshot(meta, stations, excluded, extras, cfg)
    out = {"meta": meta, "stations": stations, "excluded": excluded,
           "skipped": skipped, "extras": extras}
    with open(os.path.join(ROOT, "work", f"stations_{args.region}_{args.sol}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))
    print("snapshot:", path)
    print(f"quakes={len(extras['quakes'])} catalog_through={extras['cat_through']} "
          f"intensity_pts={len(extras['intensity'])} kp={extras['kp']}")
    print("TOP5:")
    for s in stations[:5]:
        print(f"  {s['name']} ({s['pref']}) horiz={s['horiz_mm']}mm vert={s['vert_mm']}mm")
    return 0

if __name__ == "__main__":
    sys.exit(main())
