# 地殻変動ヒートマップ（試作）

東北地方の電子基準点（GNSS連続観測点）が約1か月でどれだけ動いたかを、国土地理院の公開データから計算してヒートマップにした試作ページです。

**これは地震予測ではありません。** 電子基準点の位置の変化（地殻変動）を見える化したものです。

公開ページ: https://oosawak.github.io/geonet-heatmap/

## 計算方法

- データ: 国土地理院「電子基準点日々の座標値」F5.1解（ITRF2020）、電子基準点データ提供サービス（terras.gsi.go.jp）から取得
- 各観測点について、最新日を含む7日間の平均座標と、約30日前の7日間の平均座標の差を取り、水平変位量（mm）と上下変位（mm）を算出
- 観測点の間は IDW（逆距離加重）で補間して面として表示
- 異常に大きな変位（アンテナ交換などによる見かけの跳びの疑い）は除外

## 再現手順

```bash
python3 scripts/list_stations.py     # 東北6県の観測点一覧を取得
python3 scripts/fetch_shard.py 0 4   # .pos ファイルを data/ へ（0〜3 の4並列）
python3 scripts/fetch_shard.py 1 4
python3 scripts/fetch_shard.py 2 4
python3 scripts/fetch_shard.py 3 4
# work/fetch_result.json に統合してから
python3 scripts/compute_displacement.py
python3 scripts/build_page.py        # index.html を生成（海岸線 GeoJSON が必要）
```

海岸線は dataofjapan の都道府県 GeoJSON（Natural Earth 由来）を `work/japan_pref.geojson` に取得し、東北6県分を簡略化して埋め込んでいます。

## 出典

- 国土地理院 電子基準点日々の座標値を加工して作成（データセット DOI: https://doi.org/10.57499/GSI_GNSS_2026_001）
- 海岸線: dataofjapan/land（Natural Earth 由来）
