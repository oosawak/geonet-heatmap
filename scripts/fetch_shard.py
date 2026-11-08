#!/usr/bin/env python3
"""Shard worker: python3 fetch_shard.py K N
Downloads codes[K::N] from the stations list with its own session jar.
Solution from env GEONET_SOL (default F5.1). F5.1 goes to data/, other
solutions to data/<SOL>/. Each download unit is POST + GET retried together,
and the station ID inside the file header is verified against the request.
Region support: env GEONET_STATIONS (stations list JSON path) and
GEONET_DATA_DIR (destination dir) override the defaults."""
import subprocess, re, os, sys, time, json

BASE = "https://terras.gsi.go.jp"
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
SOL = os.environ.get("GEONET_SOL", "F5.1")
YEAR = os.environ.get("GEONET_YEAR", "2026")
STATIONS_JSON = os.path.join(ROOT, os.environ.get("GEONET_STATIONS", "work/stations_list.json"))
if os.environ.get("GEONET_DATA_DIR"):
    DATA = os.path.join(ROOT, os.environ["GEONET_DATA_DIR"])
else:
    DATA = os.path.join(ROOT, "data") if SOL == "F5.1" else os.path.join(ROOT, "data", SOL)
K, N = int(sys.argv[1]), int(sys.argv[2])
JAR = os.path.join(ROOT, "work", f"jar_shard{K}.txt")

def file_id_ok(body, cd):
    m = re.search(rb"^ ID\s+(\S+)", body, re.M)
    return bool(m) and m.group(1).decode("ascii", "replace") == cd

def curl(args, timeout=90):
    cmd = ["curl", "-s", "-m", str(timeout), "-b", JAR, "-c", JAR,
           "-e", BASE + "/pos_main.php"] + args
    return subprocess.run(cmd, capture_output=True).stdout

def main():
    stations = json.load(open(STATIONS_JSON, encoding="utf-8"))
    codes = sorted(stations)[K::N]
    if os.path.exists(JAR):
        os.remove(JAR)
    curl([BASE + "/pos_main.php", "-o", "/dev/null"], 30)
    res = {"ok": [], "not_registered": [], "failed": []}
    os.makedirs(DATA, exist_ok=True)
    yy = YEAR[-2:]
    for i, cd in enumerate(codes):
        dest = os.path.join(DATA, f"{cd}.{yy}.pos")
        if os.path.exists(dest) and os.path.getsize(dest) > 5000:
            res["ok"].append(cd); continue
        got = False; notreg = False
        for _unit in range(4):  # POST + GET as one retried unit
            html = curl([BASE + "/pos_download.php", "-X", "POST",
                         "-d", f"sol={SOL}&observation_cd={cd}&YEAR={YEAR}"], 60).decode("utf-8", "replace")
            if "未登録" in html:
                notreg = True; break
            if "unt/file_download.php" not in html:
                time.sleep(2); continue
            time.sleep(2)
            for _ in range(4):
                body = curl([BASE + "/unt/file_download.php"], 60)
                if body.startswith(b"+SITE") and b"+DATA" in body and file_id_ok(body, cd):
                    with open(dest, "wb") as f:
                        f.write(body)
                    got = True; break
                time.sleep(2)
            if got:
                break
            time.sleep(2)
        if notreg:
            res["not_registered"].append(cd)
        else:
            res["ok" if got else "failed"].append(cd)
        if (i + 1) % 15 == 0:
            print(f"shard{K} {i+1}/{len(codes)} ok={len(res['ok'])} nr={len(res['not_registered'])} fail={len(res['failed'])}", flush=True)
        time.sleep(0.2)
    tag = os.environ.get("GEONET_TAG", "")
    with open(os.path.join(ROOT, "work", f"fetch_shard{K}_{SOL}{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(f"shard{K} DONE", {k: len(v) for k, v in res.items()}, flush=True)

if __name__ == "__main__":
    main()
