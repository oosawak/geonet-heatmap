#!/usr/bin/env python3
"""Build the station list JSON from the terras prefecture filter.

Usage:
  python3 scripts/list_stations.py [--region tohoku|nankai]
  python3 scripts/list_stations.py --out work/stations_list_x.json 三重県 ...

Default (no args) keeps the original behaviour: Tohoku 6 prefectures ->
work/stations_list.json."""
import subprocess, re, os, json, argparse

BASE = "https://terras.gsi.go.jp"
ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
REGIONS = {
    "tohoku": (["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"],
               "work/stations_list.json"),
    "nankai": (["三重県", "徳島県", "香川県", "愛媛県", "高知県",
                "和歌山県", "奈良県", "滋賀県", "岐阜県", "愛知県", "静岡県",
                "兵庫県", "大阪府", "京都府", "岡山県", "広島県", "山口県",
                "大分県", "宮崎県"],
               "work/stations_list_nankai.json"),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", choices=sorted(REGIONS), default="tohoku")
    ap.add_argument("--out", default=None)
    ap.add_argument("prefs", nargs="*")
    args = ap.parse_args()
    prefs, out_rel = REGIONS[args.region]
    if args.prefs:
        prefs = args.prefs
    out_path = os.path.join(ROOT, args.out or out_rel)
    jar = out_path + ".jar"
    def curl(a, timeout=60):
        return subprocess.run(["curl", "-s", "-m", str(timeout), "-b", jar, "-c", jar,
                               "-e", BASE + "/pos_main.php"] + a, capture_output=True).stdout
    if os.path.exists(jar):
        os.remove(jar)
    curl([BASE + "/pos_main.php", "-o", "/dev/null"], 30)
    stations = {}
    for pref in prefs:
        out = curl([BASE + "/pos_main.php", "-X", "POST", "--data-urlencode", f"ken={pref}",
                    "--data-urlencode", "observation="]).decode("utf-8", "replace")
        m = re.search(r'<select name="observation_cd">(.*?)</select>', out, re.S)
        for code, _d, name in re.findall(r"<option value=([0-9A-Za-z]+)>([0-9A-Za-z]+)\(([^)]*)\)", m.group(1)):
            stations[code] = [name, pref]
        print(pref, len(stations), flush=True)
    json.dump(stations, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print("total", len(stations), "->", out_path)

if __name__ == "__main__":
    main()
