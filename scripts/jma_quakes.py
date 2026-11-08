#!/usr/bin/env python3
"""Earthquake hypocenters from JMA, two systems merged (same two-stage idea
as GEONET rapid/final solutions):

  - Formal catalog (確定値): 地震月報（カタログ編）震源データ, fixed-width
    96-byte records in zip files at
    https://www.data.jma.go.jp/eqev/data/bulletin/data/hypo/hYYYY[MM].zip
    Publication lags by months; the index page currently lists up to 2024.
  - Daily hypocenter lists (暫定値): per-day pages at
    https://www.data.jma.go.jp/eqev/data/daily_map/<YYYYMMDD>.html
    Published with ~2 days delay, covering roughly the last 90 days.

Merge rule: dates covered by the catalog use catalog values only; the daily
lists fill the period the catalog does not cover yet. Each record carries
its origin (確定 / 暫定). Max intensity is attached from JMA's earthquake
information list JSON when the event is recent enough to appear there.

Usage (CLI test):
  python3 scripts/jma_quakes.py 2026-09-11 2026-10-17 [--min-mag 3.0]
"""
import subprocess, re, sys, os, io, json, zipfile
import html as htmlmod
import datetime as dt

ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
DAILY_BASE = "https://www.data.jma.go.jp/eqev/data/daily_map"
CAT_BASE = "https://www.data.jma.go.jp/eqev/data/bulletin/data/hypo"
LIST_JSON = "https://www.jma.go.jp/bosai/quake/data/list.json"
CACHE = os.path.join(ROOT, "work", "catalog")
# fetch window: Tohoku + surrounding seas (wider than the map extent)
QLAT_MIN, QLAT_MAX, QLON_MIN, QLON_MAX = 35.5, 42.5, 138.0, 145.0
LINE = re.compile(
    r"^(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2}):(\d{2})\s+[\d.]+\s+"
    r"(\d+)°([\d.]+)'([NS])\s+(\d+)°([\d.]+)'([EW])\s+(\S+)\s+(\S+)\s+(.+)$")

def curl_bytes(url, timeout=60):
    return subprocess.run(["curl", "-s", "-m", str(timeout), url],
                          capture_output=True).stdout

def in_box(q):
    return (QLAT_MIN <= q["lat"] <= QLAT_MAX and QLON_MIN <= q["lon"] <= QLON_MAX)

# ---------- daily lists (provisional) ----------
def fetch_day(day):
    out = curl_bytes(f"{DAILY_BASE}/{day.strftime('%Y%m%d')}.html", 40).decode("utf-8", "replace")
    text = htmlmod.unescape(re.sub(r"<[^>]+>", "\n", out))
    quakes = []
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        (yy, mo, dd, hh, mi, lad, lam, ns, lod, lom, ew, dep, mag, name) = m.groups()
        try:
            magf = float(mag)
        except ValueError:
            continue
        lat = (int(lad) + float(lam) / 60.0) * (1 if ns == "N" else -1)
        lon = (int(lod) + float(lom) / 60.0) * (1 if ew == "E" else -1)
        try:
            depf = float(dep)
        except ValueError:
            depf = 0.0  # e.g. ごく浅い
        quakes.append({
            "time": f"{yy}-{int(mo):02d}-{int(dd):02d} {int(hh):02d}:{mi}",
            "name": name.strip(), "lat": round(lat, 3), "lon": round(lon, 3),
            "depth_km": depf, "mag": magf, "src": "暫定"})
    return quakes

def fetch_daily(start, end, min_mag):
    got, day = [], start
    while day <= end:
        for q in fetch_day(day):
            if in_box(q) and q["mag"] >= min_mag:
                got.append(q)
        day += dt.timedelta(days=1)
    return got

# ---------- formal catalog (final) ----------
def parse_catalog_records(raw):
    """96-byte fixed-width JMA hypocenter records (type 'J')."""
    out = []
    for l in raw.decode("ascii", "replace").splitlines():
        if len(l) < 92 or not l.startswith("J"):
            continue
        try:
            mag_s = l[52:54].strip()
            if not mag_s:
                continue
            mag = int(mag_s) / 10.0
            lat = int(l[21:24]) + int(l[24:28]) / 100.0 / 60.0
            lon = int(l[33:36]) + int(l[36:40]) / 100.0 / 60.0
            dep = int(l[44:49]) / 100.0
            t = (f"{l[1:5]}-{l[5:7]}-{l[7:9]} {l[9:11]}:{l[11:13]}")
        except ValueError:
            continue
        out.append({"time": t, "name": l[68:92].strip(), "lat": round(lat, 3),
                    "lon": round(lon, 3), "depth_km": dep, "mag": mag, "src": "確定"})
    return out

def _get_zip(name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    body = curl_bytes(f"{CAT_BASE}/{name}", 120)
    if not body.startswith(b"PK"):
        return None
    with open(path, "wb") as f:
        f.write(body)
    return path

def fetch_catalog(start, end, min_mag):
    """Returns (quakes, covered_ranges) where covered_ranges is a list of
    (date, date) the catalog files actually cover."""
    quakes, covered = [], []
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    got_months = set()
    for (yy, mm) in months:
        p = _get_zip(f"h{yy}{mm:02d}.zip")
        if p:
            got_months.add((yy, mm))
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    quakes += parse_catalog_records(z.read(n))
            covered.append((dt.date(yy, mm, 1),
                            dt.date(yy, mm, 28) + dt.timedelta(days=3)))  # month end approx, refined below
    # annual files for years whose months are all missing
    for yy in sorted({y for y, _ in months} - {y for y, _ in got_months}):
        p = _get_zip(f"h{yy}.zip")
        if p:
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    quakes += parse_catalog_records(z.read(n))
            covered.append((dt.date(yy, 1, 1), dt.date(yy, 12, 31)))
    # refine coverage to actual record dates present
    if quakes:
        days = sorted({q["time"][:10] for q in quakes})
        covered = [(dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1]))]
    seen, uniq = set(), []
    for q in quakes:
        k = (q["time"], q["lat"], q["lon"])
        if k in seen:
            continue
        seen.add(k)
        if in_box(q) and q["mag"] >= min_mag and start <= dt.date.fromisoformat(q["time"][:10]) <= end:
            uniq.append(q)
    return uniq, covered

# ---------- max intensity from JMA list JSON ----------
def attach_maxint(quakes):
    try:
        d = json.loads(curl_bytes(LIST_JSON, 40))
    except Exception:
        return
    lut = {}
    for e in d:
        at = e.get("at", "")[:16].replace("T", " ")
        if at and e.get("anm"):
            lut[(at, e["anm"])] = e.get("maxi", "")
    for q in quakes:
        q["maxint"] = lut.get((q["time"], q["name"]), "")

# ---------- merged ----------
def fetch_merged(start, end, min_mag=3.0):
    cat, covered = fetch_catalog(start, end, min_mag)
    daily = fetch_daily(start, end, min_mag)
    def in_covered(q):
        d = dt.date.fromisoformat(q["time"][:10])
        return any(a <= d <= b for a, b in covered)
    merged = cat + [q for q in daily if not in_covered(q)]
    merged.sort(key=lambda q: q["time"])
    attach_maxint(merged)
    cat_through = max((b for _, b in covered), default=None)
    return merged, (str(cat_through) if cat_through else None)

if __name__ == "__main__":
    s = dt.date.fromisoformat(sys.argv[1]); e = dt.date.fromisoformat(sys.argv[2])
    mm = float(sys.argv[sys.argv.index("--min-mag") + 1]) if "--min-mag" in sys.argv else 3.0
    qs, through = fetch_merged(s, e, mm)
    nc = sum(1 for q in qs if q["src"] == "確定")
    print(f"{len(qs)} quakes (確定 {nc} / 暫定 {len(qs) - nc}), catalog through: {through}")
    for q in sorted(qs, key=lambda q: -q["mag"])[:10]:
        print(f"  {q['time']}  M{q['mag']:.1f}  depth={q['depth_km']:.0f}km  {q['name']}  [{q['src']}]")
