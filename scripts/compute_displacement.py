#!/usr/bin/env python3
"""Parse GEONET .pos files and compute per-station displacement:
mean of latest 7 days vs mean of the 7-day window ~30 days earlier.
Outputs work/stations.json."""
import os, re, json, math, glob
import datetime as dt

ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
DATA = os.path.join(ROOT, "data")
BBOX = dict(lat_min=36.8, lat_max=41.5, lon_min=139.3, lon_max=142.3)
M_PER_DEG = 111194.9  # spherical approx, fine for differencing

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

def main():
    fetch = json.load(open(os.path.join(ROOT, "work", "fetch_result.json"), encoding="utf-8"))
    names = {c: v[0] for c, v in fetch["stations"].items()}
    prefs = {c: v[1] for c, v in fetch["stations"].items()}
    stations, excluded, skipped = [], [], []
    for path in sorted(glob.glob(os.path.join(DATA, "*.pos"))):
        code = os.path.basename(path).split(".")[0]
        jname, rows = parse_pos(path)
        if not rows:
            skipped.append((code, "no data rows")); continue
        latest = max(r[0] for r in rows)
        a = window_mean(rows, latest)                       # latest 7 days
        b = window_mean(rows, latest - dt.timedelta(days=30))  # ~30 days earlier, 7 days
        if not a or not b:
            skipped.append((code, "window shortage")); continue
        lat0 = sum(r[1] for r in rows) / len(rows)
        lon0 = sum(r[2] for r in rows) / len(rows)
        if not (BBOX["lat_min"] <= lat0 <= BBOX["lat_max"] and BBOX["lon_min"] <= lon0 <= BBOX["lon_max"]):
            skipped.append((code, "outside bbox")); continue
        dN = (a[0] - b[0]) * M_PER_DEG * 1000.0
        dE = (a[1] - b[1]) * M_PER_DEG * math.cos(math.radians(lat0)) * 1000.0
        vert = (a[2] - b[2]) * 1000.0
        horiz = math.hypot(dE, dN)
        rec = {"code": code, "name": jname or names.get(code, ""), "pref": prefs.get(code, ""),
               "lat": round(lat0, 5), "lon": round(lon0, 5),
               "dE_mm": round(dE, 1), "dN_mm": round(dN, 1),
               "horiz_mm": round(horiz, 1), "vert_mm": round(vert, 1),
               "winA": [str(a[3]), str(a[4])], "winB": [str(b[3]), str(b[4])],
               "latest": str(latest)}
        if horiz > 50 or abs(vert) > 80:
            rec["reason"] = f"horiz={horiz:.0f}mm vert={vert:.0f}mm (suspected offset)"
            excluded.append(rec)
        else:
            stations.append(rec)
    stations.sort(key=lambda s: -s["horiz_mm"])
    hs = sorted(s["horiz_mm"] for s in stations)
    def pct(q):
        return hs[min(len(hs) - 1, int(q * len(hs)))] if hs else 0
    meta = {"solution": "F5.1 (ITRF2020)", "n_stations": len(stations),
            "n_excluded": len(excluded), "n_skipped": len(skipped),
            "median_mm": hs[len(hs) // 2] if hs else 0, "p90_mm": pct(0.90), "p95_mm": pct(0.95),
            "max_mm": hs[-1] if hs else 0,
            "latest_date": max((s["latest"] for s in stations), default=None)}
    out = {"meta": meta, "stations": stations, "excluded": excluded, "skipped": skipped}
    with open(os.path.join(ROOT, "work", "stations.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))
    print("TOP10:")
    for s in stations[:10]:
        print(f"  {s['name']} ({s['pref']}) horiz={s['horiz_mm']}mm vert={s['vert_mm']}mm dE={s['dE_mm']} dN={s['dN_mm']}")
    print("EXCLUDED:", [(e["name"], e["reason"]) for e in excluded])
    print("SKIPPED:", skipped[:10], "..." if len(skipped) > 10 else "")

if __name__ == "__main__":
    main()
