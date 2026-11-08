#!/usr/bin/env python3
"""Fetch GEONET daily coordinate (.pos) files for Tohoku prefectures
from GSI's web service (terras.gsi.go.jp), F5.1 solution, year 2026.
Flow per station: POST pos_download.php -> GET unt/file_download.php (session-staged).
Uses curl (this sandbox's urllib TLS gets disconnected by the server)."""
import subprocess, re, os, sys, time, json

BASE = "https://terras.gsi.go.jp"
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
DATA = os.path.join(ROOT, "data")
JAR = os.path.join(ROOT, "work", "jar_fetch.txt")
PREFS = ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"]
SOL, YEAR = "F5.1", "2026"

def curl(args, timeout=90):
    cmd = ["curl", "-s", "-m", str(timeout), "-b", JAR, "-c", JAR,
           "-e", BASE + "/pos_main.php"] + args
    return subprocess.run(cmd, capture_output=True).stdout

def main():
    os.makedirs(DATA, exist_ok=True)
    if os.path.exists(JAR):
        os.remove(JAR)
    curl([BASE + "/pos_main.php", "-o", "/dev/null"], 30)

    # 1) station list per prefecture via the filter form
    stations = {}  # code -> (name, pref)
    for pref in PREFS:
        out = curl([BASE + "/pos_main.php", "-X", "POST",
                    "--data-urlencode", f"ken={pref}",
                    "--data-urlencode", "observation="], 60).decode("utf-8", "replace")
        m = re.search(r'<select name="observation_cd">(.*?)</select>', out, re.S)
        if not m:
            print(f"[warn] no select for {pref}", flush=True); continue
        for code, _dup, name in re.findall(r"<option value=([0-9A-Za-z]+)>([0-9A-Za-z]+)\(([^)]*)\)", m.group(1)):
            stations[code] = (name, pref)
        print(f"{pref}: cumulative {len(stations)}", flush=True)

    # 2) download each station file
    results = {"ok": [], "not_registered": [], "failed": []}
    codes = sorted(stations)
    for i, cd in enumerate(codes):
        dest = os.path.join(DATA, f"{cd}.26.pos")
        if os.path.exists(dest) and os.path.getsize(dest) > 5000:
            results["ok"].append(cd); continue
        html = curl([BASE + "/pos_download.php", "-X", "POST",
                     "-d", f"sol={SOL}&observation_cd={cd}&YEAR={YEAR}"], 60).decode("utf-8", "replace")
        if "未登録" in html:
            results["not_registered"].append(cd); continue
        if "unt/file_download.php" not in html:
            results["failed"].append(cd); continue
        got = False
        for attempt in range(8):
            body = curl([BASE + "/unt/file_download.php"], 60)
            if body.startswith(b"+SITE") and b"+DATA" in body:
                with open(dest, "wb") as f:
                    f.write(body)
                got = True; break
            time.sleep(1.5)
        results["ok" if got else "failed"].append(cd)
        if (i + 1) % 25 == 0:
            print(f"{i+1}/{len(codes)} ok={len(results['ok'])} nr={len(results['not_registered'])} fail={len(results['failed'])}", flush=True)
        time.sleep(0.2)

    meta = {"solution": SOL, "year": YEAR, "stations": {c: stations[c] for c in codes}, "results": results}
    with open(os.path.join(ROOT, "work", "fetch_result.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("DONE", {k: len(v) for k, v in results.items()}, flush=True)

if __name__ == "__main__":
    main()
