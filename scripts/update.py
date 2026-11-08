#!/usr/bin/env python3
"""Daily update pipeline (one command):
  fetch R5.1 (rapid solution) -> compute displacement -> write Markdown
  snapshot (snapshots/YYYY-MM-DD.md, the master record) -> rebuild
  index.html from snapshots -> git commit & push if anything changed.

Usage:
  python3 scripts/update.py [--sol R5.1] [--no-fetch] [--no-push]

Exit codes: 0 = updated (or nothing new), 2 = data could not be obtained
(see BLOCKER below), 1 = other failure.

BLOCKER (verified 2026-11-08): R5.1 daily coordinates are distributed
only via GSI's SFTP tree (sftp://terras.gsi.go.jp/data/coordinates_R5.1/),
which needs a personal SFTP user registration. The web download
(pos_download.php) serves only F5/F5.1; posting sol=R5.1 returns 未登録.
This script still tries the web route first (in case GSI opens it), and
also accepts .pos files dropped manually into data/R5.1/ (e.g. fetched
on a personal machine via SFTP and copied in). If neither yields files,
it exits 2 without touching the page. It never substitutes F5.1 data.
"""
import os, sys, json, glob, subprocess, argparse

ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
PY = sys.executable or "python3"

def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, **kw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sol", default="R5.1")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    sol = args.sol
    data_rel = "data" if sol == "F5.1" else f"data/{sol}"
    data_dir = os.path.join(ROOT, data_rel)

    # 1) station list
    if not os.path.exists(os.path.join(ROOT, "work", "stations_list.json")):
        if run([PY, "scripts/list_stations.py"]).returncode != 0:
            print("FAIL: station list"); return 1

    # 2) fetch (web route; POST+GET unit retries live in fetch_shard.py)
    if not args.no_fetch:
        env = dict(os.environ, GEONET_SOL=sol)
        procs = [subprocess.Popen([PY, "scripts/fetch_shard.py", str(k), "4"],
                                  cwd=ROOT, env=env) for k in range(4)]
        rcs = [p.wait() for p in procs]
        if any(rc != 0 for rc in rcs):
            print("FAIL: fetch shards", rcs); return 1
        merged = {"ok": [], "not_registered": [], "failed": []}
        for k in range(4):
            p = os.path.join(ROOT, "work", f"fetch_shard{k}_{sol}.json")
            if os.path.exists(p):
                d = json.load(open(p))
                for key in merged:
                    merged[key] += d.get(key, [])
        print("fetch:", {k: len(v) for k, v in merged.items()}, flush=True)

    # 3) do we have data?
    files = glob.glob(os.path.join(data_dir, "*.pos"))
    if len(files) < 10:
        print(f"BLOCKED: only {len(files)} .pos files in {data_rel}. "
              "R5.1 is SFTP-only distribution (registration required); "
              "the web route returned no files. Page left unchanged.")
        return 2

    # 4) compute -> Markdown snapshot (master record)
    r = run([PY, "scripts/compute_displacement.py", "--data-dir", data_rel, "--sol", sol])
    if r.returncode != 0:
        print("FAIL: compute"); return 1

    # 5) rebuild page from snapshots/*.md
    r = run([PY, "scripts/build_page.py"])
    if r.returncode != 0:
        print("FAIL: build_page"); return 1

    # 6) commit & push if changed
    if not args.no_push:
        run(["git", "add", "index.html", "snapshots", "scripts", "README.md"])
        st = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
        if st:
            run(["git", "commit", "-m", f"日次更新: {sol} スナップショット追加とページ再生成"])
            r = run(["git", "push"])
            if r.returncode != 0:
                print("FAIL: git push"); return 1
            print("pushed")
        else:
            print("no changes to commit")
    return 0

if __name__ == "__main__":
    sys.exit(main())
