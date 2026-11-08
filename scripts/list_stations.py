#!/usr/bin/env python3
"""Build work/stations_list.json from the terras prefecture filter."""
import subprocess, re, os, json
BASE = "https://terras.gsi.go.jp"
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
JAR = os.path.join(ROOT, "work", "jar_list.txt")
PREFS = ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"]
def curl(args, timeout=60):
    return subprocess.run(["curl", "-s", "-m", str(timeout), "-b", JAR, "-c", JAR,
                           "-e", BASE + "/pos_main.php"] + args, capture_output=True).stdout
if os.path.exists(JAR):
    os.remove(JAR)
curl([BASE + "/pos_main.php", "-o", "/dev/null"], 30)
stations = {}
for pref in PREFS:
    out = curl([BASE + "/pos_main.php", "-X", "POST", "--data-urlencode", f"ken={pref}",
                "--data-urlencode", "observation="]).decode("utf-8", "replace")
    m = re.search(r'<select name="observation_cd">(.*?)</select>', out, re.S)
    for code, _d, name in re.findall(r"<option value=([0-9A-Za-z]+)>([0-9A-Za-z]+)\(([^)]*)\)", m.group(1)):
        stations[code] = [name, pref]
    print(pref, len(stations), flush=True)
json.dump(stations, open(os.path.join(ROOT, "work", "stations_list.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("total", len(stations))
