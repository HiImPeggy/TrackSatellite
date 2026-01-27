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

# === 2. 定義觀測區域（台灣全島） ===
# 建立多個觀測點覆蓋台灣本島及外島（澎湖），排除金門、馬祖
# 使用網格點 + 主要城市確保完整覆蓋
taiwan_observers = {
    # 北部
    "台北": wgs84.latlon(25.03, 121.56, 0),
    "基隆": wgs84.latlon(25.13, 121.74, 0),
    "桃園": wgs84.latlon(24.99, 121.31, 0),
    "新竹": wgs84.latlon(24.80, 120.97, 0),
    
    # 中部
    "苗栗": wgs84.latlon(24.57, 120.82, 0),
    "台中": wgs84.latlon(24.15, 120.67, 0),
    "彰化": wgs84.latlon(24.08, 120.54, 0),
    "南投": wgs84.latlon(23.91, 120.68, 0),
    "雲林": wgs84.latlon(23.71, 120.43, 0),
    
    # 南部
    "嘉義": wgs84.latlon(23.48, 120.45, 0),
    "台南": wgs84.latlon(23.00, 120.23, 0),
    "高雄": wgs84.latlon(22.63, 120.30, 0),
    "屏東": wgs84.latlon(22.55, 120.55, 0),
    
    # 東部
    "宜蘭": wgs84.latlon(24.75, 121.75, 0),
    "花蓮": wgs84.latlon(23.99, 121.61, 0),
    "台東": wgs84.latlon(22.76, 121.14, 0),
    
    # 外島（澎湖）
    "澎湖": wgs84.latlon(23.57, 119.58, 0),
    
    # 補充網格點確保覆蓋完整
    "北海岸": wgs84.latlon(25.20, 121.50, 0),
    "東北角": wgs84.latlon(25.00, 122.00, 0),
    "恆春半島": wgs84.latlon(22.00, 120.75, 0),
    "綠島蘭嶼": wgs84.latlon(22.65, 121.47, 0),
}

observer_names = list(taiwan_observers.keys())
print(f"✅ 已建立 {len(taiwan_observers)} 個觀測點覆蓋台灣全島及澎湖。")

# === 3. 建立時間區間（未來 2 小時） ===
ts = load.timescale()
tz = pytz.timezone("Asia/Taipei")
t_start = ts.now()
t_end = ts.from_datetime(t_start.utc_datetime() + timedelta(hours=2))
start_time_dt = t_start.astimezone(tz)

# === 4. 第一階段：快速篩選 (Filter) ===
# 使用 find_events() 演算法，快速篩選可從台灣任一點觀測到的衛星
print(f"\n使用 find_events() 演算法，快速篩選可從台灣觀測到的衛星（從 {total_sats} 顆衛星中）...")
visible_satellites = set()  # 使用集合避免重複

# 對每個觀測點進行篩選
for observer_name, observer in tqdm(taiwan_observers.items(), desc="-> 檢查各觀測點", unit=" 個觀測點"):
    for sat in stations:
        # 尋找衛星仰角 > 20 度的事件
        t, events = sat.find_events(observer, t_start, t_end, altitude_degrees=20.0)
        # 0=升起, 1=最高點, 2=落下
        # 如果有升起事件，代表該衛星會經過該觀測點上空
        if 0 in events:
            visible_satellites.add(sat)

visible_satellites = list(visible_satellites)
visible_count = len(visible_satellites)
print(f"\n✅ 計算完成！在未來 2 小時內，共找到 {visible_count} 顆衛星會經過台灣上空。")

# === 5. 第二階段：計算詳細位置 ===
# 對每顆可見衛星，記錄其從所有台灣觀測點的可見情況
print(f"\n正在計算這 {visible_count} 顆衛星的每分鐘詳細軌跡（從所有台灣觀測點）...")
visible_log = []

# 建立每分鐘的時間點
minutes = [start_time_dt + timedelta(minutes=i) for i in range(0, 120, 1)]  # 每分鐘
times_utc = ts.from_datetimes(minutes)

# 針對可見的衛星進行詳細計算
for sat in tqdm(visible_satellites, desc="-> 計算詳細軌跡", unit=" 顆衛星"):
    sat_name = sat.name
    
    # 取得衛星在地心座標系統的位置（所有觀測點共用）
    geocentric = sat.at(times_utc)
    position = geocentric.position.km
    x_ecef = position[0]
    y_ecef = position[1]
    z_ecef = position[2]
    
    subpoints = geocentric.subpoint()
    latitudes = subpoints.latitude.degrees
    longitudes = subpoints.longitude.degrees
    heights = subpoints.elevation.km
    
    # 對每個觀測點計算可見性
    for observer_name, observer in taiwan_observers.items():
        difference = sat - observer
        elevations, azimuths, distances = difference.at(times_utc).altaz()
        
        for i, el in enumerate(elevations.degrees):
            if el > 0:  # 衛星在地平線以上
                t_str = minutes[i].strftime("%Y-%m-%d %H:%M:%S")
                visible_log.append({
                    "time": t_str,
                    "satellite": sat_name,
                    "observer_location": observer_name,  # 新增：觀測點名稱
                    "elevation_deg": round(el, 2),
                    "azimuth_deg": round(azimuths.degrees[i], 2),
                    "distance_km": round(distances.km[i], 2),
                    "lat_subpoint": round(latitudes[i], 2),
                    "lon_subpoint": round(longitudes[i], 2),
                    "height_km": round(heights[i], 2),
                    "x_ecef_km": round(x_ecef[i], 2),
                    "y_ecef_km": round(y_ecef[i], 2),
                    "z_ecef_km": round(z_ecef[i], 2)
                })

# === 6. 顯示結果並匯出 ===
if not visible_log:
    print("❌ 沒有衛星經過台灣上空")
else:
    print(f"\n✅ 共 {len(visible_log)} 筆可見衛星資料點（2小時內，涵蓋所有台灣觀測點）")

    # 按時間排序
    visible_log.sort(key=lambda x: (x['time'], x['satellite'], x['observer_location']))

    # 建立輸出目錄
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    # 匯出完整資料（包含所有觀測點）
    output_file_full = os.path.join(OUT_DIR, "visible_satellites_taiwan_full.csv")
    with open(output_file_full, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=visible_log[0].keys())
        writer.writeheader()
        writer.writerows(visible_log)
    print(f"已匯出完整結果到 {output_file_full}")

    # === 額外功能：產生簡化版（每個時間點每顆衛星只保留最佳觀測點） ===
    # 最佳觀測點定義：仰角最高的觀測點
    best_observations = {}
    for entry in visible_log:
        key = (entry['time'], entry['satellite'])
        if key not in best_observations or entry['elevation_deg'] > best_observations[key]['elevation_deg']:
            best_observations[key] = entry
    
    simplified_log = list(best_observations.values())
    simplified_log.sort(key=lambda x: (x['time'], x['satellite']))
    
    output_file_simplified = os.path.join(OUT_DIR, "visible_satellites_taiwan_best.csv")
    with open(output_file_simplified, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=simplified_log[0].keys())
        writer.writeheader()
        writer.writerows(simplified_log)
    print(f"已匯出最佳觀測點結果到 {output_file_simplified}")
    
    # 統計資訊
    unique_satellites = len(set(entry['satellite'] for entry in visible_log))
    print(f"\n📊 統計資訊：")
    print(f"   - 可見衛星總數: {unique_satellites} 顆")
    print(f"   - 總觀測記錄數: {len(visible_log)} 筆（包含所有觀測點）")
    print(f"   - 最佳觀測記錄數: {len(simplified_log)} 筆（每衛星每時間點選最高仰角）")
