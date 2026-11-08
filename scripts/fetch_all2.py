#!/usr/bin/env python3
"""Single-process fetcher with (POST+GET) retry units and station-ID verification.
Writes work/fetch_result.json at the end (compatible with compute_displacement.py)."""
import subprocess, os, time, json

BASE = "https://terras.gsi.go.jp"
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
DATA = os.path.join(ROOT, "data")
JAR = os.path.join(ROOT, "work", "jar_all.txt")
SOL, YEAR = "F5.1", "2026"

def curl(args, timeout=90):
    cmd = ["curl", "-s", "-m", str(timeout), "-b", JAR, "-c", JAR,
           "-e", BASE + "/pos_main.php"] + args
    return subprocess.run(cmd, capture_output=True).stdout

def main():
    stations = json.load(open(os.path.join(ROOT, "work", "stations_list.json"), encoding="utf-8"))
    if os.path.exists(JAR):
        os.remove(JAR)
    curl([BASE + "/pos_main.php", "-o", "/dev/null"], 30)
    res = {"ok": [], "not_registered": [], "failed": []}
    codes = sorted(stations)
    for i, cd in enumerate(codes):
        dest = os.path.join(DATA, f"{cd}.26.pos")
        if os.path.exists(dest) and os.path.getsize(dest) > 5000:
            res["ok"].append(cd); continue
        status = "failed"
        for attempt in range(7):
            html = curl([BASE + "/pos_download.php", "-X", "POST",
                         "-d", f"sol={SOL}&observation_cd={cd}&YEAR={YEAR}"], 60).decode("utf-8", "replace")
            if "未登録" in html:
                status = "not_registered"; break
            if "unt/file_download.php" not in html:
                time.sleep(1.5); continue
            body = curl([BASE + "/unt/file_download.php"], 60)
            if body.startswith(b"+SITE") and b"+DATA" in body and (f"ID           {cd}" in body.decode("utf-8", "replace")[:200]):
                with open(dest, "wb") as f:
                    f.write(body)
                status = "ok"; break
            time.sleep(1.5)
        res[status].append(cd)
        if (i + 1) % 20 == 0:
            print(f"{i+1}/{len(codes)} ok={len(res['ok'])} nr={len(res['not_registered'])} fail={len(res['failed'])}", flush=True)
        time.sleep(0.3)
    out = {"solution": SOL, "year": YEAR, "stations": stations, "results": res}
    json.dump(out, open(os.path.join(ROOT, "work", "fetch_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("DONE", {k: len(v) for k, v in res.items()}, flush=True)

if __name__ == "__main__":
    main()
