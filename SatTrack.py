from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import pytz
import csv
from tqdm import tqdm 
import os

OUT_DIR = "output"

# === 1. 載入最新 TLE ===
stations = load.tle_file("https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle")
total_sats = len(stations)
print(f"✅ 成功下載 {total_sats} 組 TLE 資料。")

# === 2. 定義觀測點（新竹） ===
hsinchu = wgs84.latlon(24.8, 120.97, 0)

# === 3. 建立時間區間（未來 2 小時） ===
ts = load.timescale()
tz = pytz.timezone("Asia/Taipei")
t_start = ts.now()  # 改用 skyfield 的
t_end = ts.from_datetime(t_start.utc_datetime() + timedelta(hours=2))
start_time_dt = t_start.astimezone(tz) # 用於後續計算

# === 4. 第一階段：快速篩選 (Filter) ===
#    使用 find_events() 演算法，快速篩選 8521 顆衛星...
print(f"\n使用 find_events() 演算法，快速篩選 {total_sats} 顆衛星...")
visible_satellites = []
# 使用 tqdm 顯示進度條
for sat in tqdm(stations, desc="-> 處理進度", unit=" 顆衛星"):
    # 尋找衛星仰角 > 0 (地平線以上) 的事件
    t, events = sat.find_events(hsinchu, t_start, t_end, altitude_degrees=20.0)
    # 0=升起, 1=最高點, 2=落下
    # 如果 0 (升起) 事件存在，代表它會經過
    if 0 in events:
        visible_satellites.append(sat)

visible_count = len(visible_satellites)
print(f"\n✅ 計算完成！在未來 2 小時內，共找到 {visible_count} 顆衛星會經過新竹上空。")


# === 5. 第二階段：計算詳細位置 ===
print(f"\n正在計算這 {visible_count} 顆衛星的每分鐘詳細軌跡...")
visible_log = []

# 建立每分鐘的時間點
minutes = [start_time_dt + timedelta(minutes=i) for i in range(0, 120, 1)]  # 每分鐘
times_utc = ts.from_datetimes(minutes) # 轉換為 skyfield 的時間物件

# 只針對可見的衛星進行詳細計算
for sat in tqdm(visible_satellites, desc="-> 計算詳細軌跡", unit=" 顆衛星"):
    sat_name = sat.name
    difference = sat - hsinchu
    
    # 這裡我們一次取得 仰角(elevation)、方位角(azimuth)、斜距(distance)
    elevations, azimuths, distances = difference.at(times_utc).altaz()
    
    subpoints = sat.at(times_utc).subpoint()
    latitudes = subpoints.latitude.degrees
    longitudes = subpoints.longitude.degrees
    heights = subpoints.elevation.km

    for i, el in enumerate(elevations.degrees):
        if el > 0:  # 衛星在地平線以上
            t_str = minutes[i].strftime("%Y-%m-%d %H:%M:%S")
            visible_log.append({
                "time": t_str,
                "satellite": sat_name,
                "elevation_deg": round(el, 2),        # elevation_deg (仰角)： 您要抬頭多高
                "azimuth_deg": round(azimuths.degrees[i], 2), # azimuth_deg (方位角)： 您要面向哪個羅盤方向？
                "distance_km": round(distances.km[i], 2), # distance_km (斜距)： 衛星離您有多遠？
                "lat_subpoint": round(latitudes[i], 2),  # lat_subpoint (星下點緯度): 衛星飛在地球上哪個緯度的上空？
                "lon_subpoint": round(longitudes[i], 2),  # lon_subpoint (星下點經度)：衛星飛在地球上哪個經度的上空？
                "height_km": round(heights[i], 2) # height_km (衛星高度)：距離地表有多遠
            })

# === 6. 顯示結果 ===

if not visible_log:
    print("❌ 沒有衛星經過新竹上空")
else:
    # for entry in visible_log[:5]:
    #     # 修正：更新 print 內容以包含新資訊
    #     print(f"[{entry['time']}] {entry['satellite']}: "
    #           f"仰角(el)={entry['elevation_deg']}° "
    #           f"方位(az)={entry['azimuth_deg']}° "
    #           f"斜距(dist)={entry['distance_km']}km "
    #           f"星下點=({entry['lat_subpoint']}, {entry['lon_subpoint']}) "
    #           f"高度={entry['height_km']}km")

    print(f"\n✅ 共 {len(visible_log)} 筆可見衛星資料點（2小時內）")

    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    output_file = os.path.join(OUT_DIR, "visible_satellites_hsinchu.csv")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=visible_log[0].keys())
        writer.writeheader()
        writer.writerows(visible_log)

    print(f"已匯出結果到 {output_file}")