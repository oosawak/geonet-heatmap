#!/usr/bin/env python3
"""Observed seismic intensity (震度) from JMA earthquake information JSON.

Route: https://www.jma.go.jp/bosai/quake/data/list.json (recent events,
roughly the last 30 days) -> per-event detail JSON, whose
Body.Intensity.Observation tree carries each station's name, lat/lon and
observed intensity. Aggregates, per station in the 6 Tohoku prefectures,
the maximum intensity observed inside the requested window.

Coverage is limited by how far list.json reaches back; the actually
covered window is returned and must be stated in the snapshot.
"""
import subprocess, json
import datetime as dt

LIST_JSON = "https://www.jma.go.jp/bosai/quake/data/list.json"
DETAIL = "https://www.jma.go.jp/bosai/quake/data/"
PREFS = {"青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"}
RANK = {"1": 1, "2": 2, "3": 3, "4": 4, "5-": 4.5, "5+": 5.0,
        "6-": 5.5, "6+": 6.0, "7": 7.0}

def curl_json(url):
    out = subprocess.run(["curl", "-s", "-m", "40", url], capture_output=True).stdout
    return json.loads(out)

PREF_CODES = {"02", "03", "04", "05", "06", "07"}  # Tohoku in list.json int[]

def fetch_intensity(start, end, min_rank=3):
    """start/end: dt.date. Returns (points, covered_start, covered_end, period_max).
    points: [{name, city, pref, lat, lon, maxint, count}] sorted by rank desc.
    period_max: largest intensity string observed anywhere in Tohoku during
    the covered window (from list.json prefecture maxima), or None."""
    entries = curl_json(LIST_JSON)
    if not entries:
        return [], None, None, None
    times = [dt.datetime.fromisoformat(e["at"]).date() for e in entries if e.get("at")]
    covered_start = max(start, min(times))
    covered_end = min(end, max(times))
    period_max = None
    for e in entries:
        at = dt.datetime.fromisoformat(e["at"]).date()
        if not (covered_start <= at <= covered_end):
            continue
        for p in e.get("int", []):
            if p.get("code") in PREF_CODES and p.get("maxi"):
                if period_max is None or RANK.get(p["maxi"], 0) > RANK.get(period_max, 0):
                    period_max = p["maxi"]
    stations = {}
    for e in entries:
        if not e.get("json"):
            continue
        at = dt.datetime.fromisoformat(e["at"]).date()
        if not (covered_start <= at <= covered_end):
            continue
        try:
            d = curl_json(DETAIL + e["json"])
        except Exception:
            continue
        obs = (d.get("Body", {}).get("Intensity", {}) or {}).get("Observation", {}) or {}
        for pref in obs.get("Pref", []):
            if pref.get("Name") not in PREFS:
                continue
            for area in pref.get("Area", []):
                for city in area.get("City", []):
                    for st in city.get("IntensityStation", []):
                        inten = st.get("Int", "")
                        if RANK.get(inten, 0) < min_rank:
                            continue
                        ll = st.get("latlon", {})
                        key = st.get("Code") or st.get("Name")
                        rec = stations.get(key)
                        if rec is None:
                            rec = {"name": st.get("Name", ""), "city": city.get("Name", ""),
                                   "pref": pref.get("Name", ""),
                                   "lat": ll.get("lat"), "lon": ll.get("lon"),
                                   "maxint": inten, "count": 0}
                            stations[key] = rec
                        if RANK[inten] > RANK[rec["maxint"]]:
                            rec["maxint"] = inten
                        rec["count"] += 1
    pts = [r for r in stations.values() if r["lat"] is not None]
    pts.sort(key=lambda r: (-RANK[r["maxint"]], r["pref"], r["name"]))
    return pts, str(covered_start), str(covered_end), period_max

if __name__ == "__main__":
    import sys
    s = dt.date.fromisoformat(sys.argv[1]); e = dt.date.fromisoformat(sys.argv[2])
    pts, cs, ce, pm = fetch_intensity(s, e)
    print(f"{len(pts)} stations, covered {cs} .. {ce}, period max intensity {pm}")
    for p in pts[:15]:
        print(f"  震度{p['maxint']}  {p['name']} ({p['city']}, {p['pref']}) x{p['count']}")
