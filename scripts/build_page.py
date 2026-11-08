#!/usr/bin/env python3
"""Build index.html: simplified Tohoku coastline + stations.json -> self-contained page."""
import json, math, os
from collections import Counter

ROOT = os.path.expanduser("~/workspace/geonet-heatmap")
LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = 139.3, 142.3, 36.8, 41.5
PREFS = ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"]

def dp_simplify(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        denom = math.hypot(dx, dy)
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if denom == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / denom
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol and idx > 0:
            keep[idx] = True
            stack.append((a, idx)); stack.append((idx, b))
    return [p for p, k in zip(pts, keep) if k]

def load_coast():
    d = json.load(open(os.path.join(ROOT, "work", "japan_pref.geojson"), encoding="utf-8"))
    rings = []
    def add_ring(ring):
        if len(ring) < 4:
            return
        lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
        if max(lons) < LON_MIN - 0.4 or min(lons) > LON_MAX + 0.4 or max(lats) < LAT_MIN - 0.4 or min(lats) > LAT_MAX + 0.4:
            return
        simp = dp_simplify([(round(x, 4), round(y, 4)) for x, y in ring], 0.0018)
        if len(simp) >= 3:
            rings.append([[x, y] for x, y in simp])
    for f in d["features"]:
        if f["properties"].get("nam_ja") not in PREFS:
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly:
                add_ring(ring)
    return rings

def main():
    data = json.load(open(os.path.join(ROOT, "work", "stations.json"), encoding="utf-8"))
    meta, stations = data["meta"], data["stations"]
    coast = load_coast()
    latest = Counter(s["latest"] for s in stations).most_common(1)[0][0]
    a = Counter(tuple(s["winA"]) for s in stations).most_common(1)[0][0]
    b = Counter(tuple(s["winB"]) for s in stations).most_common(1)[0][0]
    vmax = max(10.0, math.ceil(meta["p95_mm"]))
    dirs = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]
    for s in stations:
        ang = math.degrees(math.atan2(s["dE_mm"], s["dN_mm"])) % 360
        s["dir"] = dirs[int((ang + 22.5) // 45) % 8]
    top = stations[:8]
    top_rows = "\n".join(
        f"<tr><td>{s['name']}</td><td>{s['pref']}</td><td class='num'>{s['horiz_mm']:.1f}</td>"
        f"<td>{s['dir']}</td><td class='num'>{s['vert_mm']:+.1f}</td></tr>" for s in top)
    html = TEMPLATE
    html = html.replace("__STATIONS__", json.dumps(
        [{"lat": s["lat"], "lon": s["lon"], "h": s["horiz_mm"], "n": s["name"]} for s in stations],
        ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__COAST__", json.dumps(coast, separators=(",", ":")))
    html = html.replace("__VMAX__", str(vmax))
    html = html.replace("__N__", str(meta["n_stations"]))
    html = html.replace("__NEX__", str(meta["n_excluded"]))
    html = html.replace("__WINA__", f"{a[0]} 〜 {a[1]}")
    html = html.replace("__WINB__", f"{b[0]} 〜 {b[1]}")
    html = html.replace("__LATEST__", latest)
    html = html.replace("__TOPROWS__", top_rows)
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html written: stations={meta['n_stations']} coast_rings={len(coast)} vmax={vmax} latest={latest}")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>地殻変動ヒートマップ（試作）― 東北の電子基準点</title>
<style>
  :root { --ink:#1a2733; --sub:#5a6b7a; --line:#d5dde3; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; color:var(--ink); background:#fff; }
  .wrap { max-width:1180px; margin:0 auto; padding:16px; }
  h1 { font-size:1.45rem; margin:0 0 4px; }
  .lead { color:var(--sub); margin:0 0 12px; font-size:.92rem; }
  .notice { border:1.5px solid #c0392b; background:#fdf0ee; color:#7b241c; border-radius:8px; padding:10px 12px; font-size:.92rem; margin:0 0 14px; }
  .layout { display:flex; gap:18px; align-items:flex-start; }
  .mapbox { flex:1 1 560px; min-width:300px; }
  canvas#map { width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:8px; }
  .side { flex:1 1 340px; min-width:280px; font-size:.9rem; }
  .legend { margin:10px 0 4px; }
  .legend .bar { height:14px; border-radius:4px; border:1px solid var(--line);
    background:linear-gradient(90deg,#313695,#4575b4,#74add1,#abd9e9,#e0f3f8,#ffffbf,#fee090,#fdae61,#f46d43,#d73027,#a50026); }
  .legend .scale { display:flex; justify-content:space-between; color:var(--sub); font-size:.8rem; margin-top:2px; }
  h2 { font-size:1.02rem; border-bottom:2px solid var(--line); padding-bottom:4px; margin:18px 0 8px; }
  table { border-collapse:collapse; width:100%; }
  th, td { border-bottom:1px solid var(--line); padding:5px 6px; text-align:left; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  .meta { color:var(--sub); font-size:.85rem; line-height:1.7; }
  footer { margin-top:22px; border-top:1px solid var(--line); padding-top:10px; color:var(--sub); font-size:.82rem; line-height:1.7; }
  @media (max-width: 760px) { .layout { flex-direction:column; } .side, .mapbox { width:100%; } }
</style>
</head>
<body>
<div class="wrap">
  <h1>地殻変動ヒートマップ（試作）</h1>
  <p class="lead">東北地方の電子基準点（GNSS連続観測点）が、約1か月でどれだけ動いたかを見える化したものです。</p>
  <p class="notice">これは地震予測ではありません。電子基準点の位置の変化を見える化したものです。色は「地面の動きの大きさ」を表し、地震の起きやすさを表すものではありません。</p>
  <div class="layout">
    <div class="mapbox">
      <canvas id="map"></canvas>
      <div class="legend">
        <div class="bar"></div>
        <div class="scale"><span>0 mm（ほぼ動いていない）</span><span>水平変位量</span><span>__VMAX__ mm 以上</span></div>
      </div>
    </div>
    <div class="side">
      <h2>この図について</h2>
      <p class="meta">
        対象期間: __WINB__ の7日間平均 と __WINA__ の7日間平均 の差（データ最新日: __LATEST__）<br>
        観測点数: __N__ 点（東北6県・対象範囲内）<br>
        解の種類: F5.1解（ITRF2020）<br>
        計算方法: 各観測点で2つの期間の平均座標の差を取り、水平変位量（mm）を算出。観測点の間は IDW（逆距離加重）で補間して面にしています。丸い点が電子基準点の位置です。<br>
        異常に大きな変位を示した __NEX__ 点は、アンテナ交換などによる見かけの跳びの疑いとして除外しました。
      </p>
      <h2>変位の大きい観測点（上位8点）</h2>
      <table>
        <tr><th>観測点</th><th>県</th><th class="num">水平 (mm)</th><th>向き</th><th class="num">上下 (mm)</th></tr>
        __TOPROWS__
      </table>
      <p class="meta">上下はプラスが隆起、マイナスが沈降です。今回の期間では、岩手県を中心とする地域で動きが大きく、日本海側は小さめでした。東北では2011年の東北地方太平洋沖地震の余効変動（地震後に地面がゆっくり動き続ける現象）が今も続いていて、こうした月単位の動きの一部になっています。</p>
    </div>
  </div>
  <footer>
    出典: 国土地理院 電子基準点日々の座標値を加工して作成（電子基準点データ提供サービス、F5.1解）<br>
    データセット DOI: https://doi.org/10.57499/GSI_GNSS_2026_001 ／ 海岸線: Natural Earth 由来の都道府県境界データ（dataofjapan）を簡略化<br>
    試作ページです。数値は7日間平均同士の差で、観測誤差（数mm程度）を含みます。
  </footer>
</div>
<script>
const STATIONS = __STATIONS__;
const COAST = __COAST__;
const VMAX = __VMAX__;
const LON_MIN = 139.3, LON_MAX = 142.3, LAT_MIN = 36.8, LAT_MAX = 41.5;
const KX = Math.cos(39.15 * Math.PI / 180);
const PW = (LON_MAX - LON_MIN) * KX, PH = LAT_MAX - LAT_MIN;
const STOPS = [[49,54,149],[69,117,180],[116,173,209],[171,217,233],[224,243,248],[255,255,191],[254,224,144],[253,174,97],[244,109,67],[215,48,39],[165,0,38]];
function colorAt(t) {
  t = Math.max(0, Math.min(1, t));
  const x = t * (STOPS.length - 1), i = Math.min(STOPS.length - 2, Math.floor(x)), f = x - i;
  const a = STOPS[i], b = STOPS[i + 1];
  return `rgb(${Math.round(a[0]+(b[0]-a[0])*f)},${Math.round(a[1]+(b[1]-a[1])*f)},${Math.round(a[2]+(b[2]-a[2])*f)})`;
}
function proj(lon, lat, W, H) {
  return [ (lon - LON_MIN) * KX / PW * W, (LAT_MAX - lat) / PH * H ];
}
function inRing(x, y, ring, W, H) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = proj(ring[i][0], ring[i][1], W, H);
    const [xj, yj] = proj(ring[j][0], ring[j][1], W, H);
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}
function onLand(px, py, W, H) {
  let inside = false;
  for (const ring of COAST) if (inRing(px, py, ring, W, H)) inside = !inside;
  return inside;
}
function draw() {
  const cv = document.getElementById('map');
  const box = cv.parentElement.getBoundingClientRect();
  const cssW = Math.max(300, box.width);
  const cssH = cssW * PH / PW;
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.round(cssW * dpr); cv.height = Math.round(cssH * dpr);
  cv.style.height = cssH + 'px';
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = cssW, H = cssH;
  ctx.fillStyle = '#dceef7'; ctx.fillRect(0, 0, W, H);
  // land base
  ctx.beginPath();
  for (const ring of COAST) {
    ring.forEach((p, i) => { const [x, y] = proj(p[0], p[1], W, H); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.closePath();
  }
  ctx.fillStyle = '#f4f1e8'; ctx.fill('evenodd');
  // IDW heat cells clipped to land
  const cell = PW / 46; // projected units
  const cols = Math.ceil(PW / cell), rows = Math.ceil(PH / cell);
  const cw = W / cols, ch = H / rows;
  ctx.save();
  ctx.beginPath();
  for (const ring of COAST) {
    ring.forEach((p, i) => { const [x, y] = proj(p[0], p[1], W, H); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.closePath();
  }
  ctx.clip('evenodd');
  const sp = STATIONS.map(s => ({ x: (s.lon - LON_MIN) * KX, y: s.lat - LAT_MIN, h: s.h }));
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const gx = (c + 0.5) * cell, gy = PH - (r + 0.5) * cell;
      const px = gx / PW * W, py = (r + 0.5) * ch;
      let sw = 0, sv = 0, dmin = 1e9;
      for (const s of sp) {
        const dx = s.x - gx, dy = s.y - gy;
        const d2 = dx * dx + dy * dy;
        if (d2 < dmin) dmin = d2;
        if (d2 < 0.72) { const w = 1 / (d2 + 0.004); sw += w; sv += w * s.h; }
      }
      if (sw === 0 || dmin > 0.30) continue;
      ctx.fillStyle = colorAt((sv / sw) / VMAX);
      ctx.fillRect(c * cw - 0.5, r * ch - 0.5, cw + 1, ch + 1);
    }
  }
  ctx.restore();
  // coastline stroke
  ctx.beginPath();
  for (const ring of COAST) {
    ring.forEach((p, i) => { const [x, y] = proj(p[0], p[1], W, H); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.closePath();
  }
  ctx.strokeStyle = 'rgba(70,80,90,0.65)'; ctx.lineWidth = 0.8; ctx.stroke();
  // stations
  for (const s of STATIONS) {
    const [x, y] = proj(s.lon, s.lat, W, H);
    ctx.beginPath(); ctx.arc(x, y, 2.1, 0, 7);
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.strokeStyle = '#333'; ctx.lineWidth = 0.7; ctx.stroke();
  }
  // scale bar (50 km ~ 0.45 deg lat) and north
  const km50 = 0.45 / PH * H;
  const bx = W - 70, by = H - 18;
  ctx.strokeStyle = '#333'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx, by - km50); ctx.stroke();
  ctx.fillStyle = '#333'; ctx.font = '11px sans-serif';
  ctx.fillText('50 km', bx + 6, by - km50 / 2 + 4);
  ctx.font = 'bold 14px sans-serif'; ctx.fillText('N ↑', 10, 22);
}
window.addEventListener('resize', draw);
draw();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
