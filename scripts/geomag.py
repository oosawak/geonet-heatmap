#!/usr/bin/env python3
"""Geomagnetic activity: Kp index from GFZ (German Research Centre for
Geosciences), nowcast text file. Returns the day's maximum 3-hourly Kp.
Kakioka (JMA) was checked first; its K-index pages render data via a
viewer without a plain machine-readable endpoint, so GFZ is used."""
import subprocess
import datetime as dt

URL = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_nowcast.txt"

def kp_for_date(day):
    """day: dt.date -> max Kp (float) or None."""
    out = subprocess.run(["curl", "-s", "-m", "40", URL],
                         capture_output=True).stdout.decode("ascii", "replace")
    for line in out.splitlines():
        t = line.split()
        if len(t) < 15:
            continue
        try:
            if (int(t[0]), int(t[1]), int(t[2])) != (day.year, day.month, day.day):
                continue
            vals = [float(x) for x in t[7:15]]
        except ValueError:
            continue
        vals = [v for v in vals if v >= 0]
        return max(vals) if vals else None
    return None

if __name__ == "__main__":
    import sys
    d = dt.date.fromisoformat(sys.argv[1])
    print(d, kp_for_date(d))
