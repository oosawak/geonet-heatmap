#!/usr/bin/env python3
"""Shard worker: python3 fetch_shard.py K N
Downloads codes[K::N] from work/stations_list.json with its own session jar."""
import subprocess, re, os, sys, time, json

BASE = "https://terras.gsi.go.jp"
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
DATA = os.path.join(ROOT, "data")
SOL, YEAR = "F5.1", "2026"
K, N = int(sys.argv[1]), int(sys.argv[2])
JAR = os.path.join(ROOT, "work", f"jar_shard{K}.txt")

def curl(args, timeout=90):
    cmd = ["curl", "-s", "-m", str(timeout), "-b", JAR, "-c", JAR,
           "-e", BASE + "/pos_main.php"] + args
    return subprocess.run(cmd, capture_output=True).stdout

def main():
    stations = json.load(open(os.path.join(ROOT, "work", "stations_list.json"), encoding="utf-8"))
    codes = sorted(stations)[K::N]
    if os.path.exists(JAR):
        os.remove(JAR)
    curl([BASE + "/pos_main.php", "-o", "/dev/null"], 30)
    res = {"ok": [], "not_registered": [], "failed": []}
    for i, cd in enumerate(codes):
        dest = os.path.join(DATA, f"{cd}.26.pos")
        if os.path.exists(dest) and os.path.getsize(dest) > 5000:
            res["ok"].append(cd); continue
        html = curl([BASE + "/pos_download.php", "-X", "POST",
                     "-d", f"sol={SOL}&observation_cd={cd}&YEAR={YEAR}"], 60).decode("utf-8", "replace")
        if "未登録" in html:
            res["not_registered"].append(cd); continue
        if "unt/file_download.php" not in html:
            res["failed"].append(cd); continue
        got = False
        time.sleep(2)
        for _ in range(6):
            body = curl([BASE + "/unt/file_download.php"], 60)
            if body.startswith(b"+SITE") and b"+DATA" in body:
                with open(dest, "wb") as f:
                    f.write(body)
                got = True; break
            time.sleep(2)
        res["ok" if got else "failed"].append(cd)
        if (i + 1) % 15 == 0:
            print(f"shard{K} {i+1}/{len(codes)} ok={len(res['ok'])} nr={len(res['not_registered'])} fail={len(res['failed'])}", flush=True)
        time.sleep(0.2)
    with open(os.path.join(ROOT, "work", f"fetch_shard{K}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(f"shard{K} DONE", {k: len(v) for k, v in res.items()}, flush=True)

if __name__ == "__main__":
    main()
