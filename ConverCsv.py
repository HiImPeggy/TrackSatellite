import pandas as pd
import json
from datetime import datetime
import os

INPUT_CSV = "output/visible_satellites_hsinchu.csv"
OUT_DIR = "output"

print(f"Loading data from {INPUT_CSV}...")
try:
    df = pd.read_csv(INPUT_CSV)
except FileNotFoundError:
    print(f"錯誤：找不到檔案 '{INPUT_CSV}'。請確認檔案名稱和路徑是否正確。")
    exit()

# 確保時間欄位被正確解析為 datetime 物件
df['time'] = pd.to_datetime(df['time'])

# 取得模擬的開始與結束時間 (ISO 8601 格式)
start_time = df['time'].min().isoformat() + "Z"
end_time = df['time'].max().isoformat() + "Z"

# CZML 檔案的 "骨架"
czml = []

# --- 1. Document Packet (文件標頭) ---
# 這定義了整個場景的名稱、時間範圍和時鐘設定
doc_packet = {
    "id": "document",
    "name": "Starlink Orbits over Hsinchu",
    "version": "1.0",
    "clock": {
        "interval": f"{start_time}/{end_time}",
        "currentTime": start_time,
        "multiplier": 30,  # 播放速度
        "range": "LOOP_STOP"
    }
}
czml.append(doc_packet)

# --- 2. Hsinchu Location Packet (新竹標示點) ---
hsinchu_packet = {
    "id": "hsinchu",
    "name": "Hsinchu (觀測點)",
    "position": {
        "cartographicDegrees": [120.97, 24.8, 0] # 經度, 緯度, 高度(米)
    },
    "point": {
        "color": {"rgba": [255, 128, 0, 255]}, 
        "pixelSize": 15
    },
    "label": {
        "text": "Hsinchu",
        "fillColor": {"rgba": [255, 128, 0, 255]},
        "font": "12pt sans-serif",
        "pixelOffset": {"cartesian2": [0, -20]}
    }
}
czml.append(hsinchu_packet)


# --- 3. Satellite Packets (衛星封包) ---
print(f"Processing {df['satellite'].nunique()} unique satellites...")

# 依據衛星名稱分組
grouped = df.groupby('satellite')

for sat_name, sat_data in grouped:
    
    # 建立這顆衛星的時間序列資料
    # 格式: [time_iso, lon, lat, alt_meters, time_iso, lon, lat, alt_meters, ...]
    position_data = []
    
    # 這顆衛星第一次和最後一次出現的時間
    sat_start_time = sat_data['time'].min().isoformat() + "Z"
    sat_end_time = sat_data['time'].max().isoformat() + "Z"
    
    for _, row in sat_data.iterrows():
        time_iso = row['time'].isoformat() + "Z"
        position_data.append(time_iso)
        position_data.append(row['lon_subpoint'])
        position_data.append(row['lat_subpoint'])
        position_data.append(row['height_km'] * 1000) # CZML 需要公尺(meters)
        
    # 建立這顆衛星的 CZML 封包
    sat_packet = {
        "id": sat_name,
        "name": sat_name,
        "availability": f"{sat_start_time}/{sat_end_time}", # 衛星可見的時間
        "model": { # 使用 Cesium 內建的衛星模型
            "gltf": "data:application/octet-stream;base64,eyJBTkciOiJUaGlzIGlzIGEgcGxhY2Vob2xkZXIgZm9yIGEgc2F0ZWxsaXRlIG1vZGVsLiJ9",
            "minimumPixelSize": 64
        },
        "path": { # 顯示衛星的軌跡
            "material": {
                "solidColor": {
                    "color": {"rgba": [77, 255, 255, 100]} 
                }
            },
            "width": 1,
            "leadTime": 3600, # 顯示未來 1 小時的軌跡
            "trailTime": 0 
        },
        "label": { # 顯示衛星名稱
            "text": sat_name,
            "fillColor": {"rgba": [255, 255, 255, 255]},
            "font": "10pt sans-serif",
            "horizontalOrigin": "LEFT",
            "pixelOffset": {"cartesian2": [12, 0]}
        },
        "position": {
            "cartographicDegrees": position_data
        }
    }
    czml.append(sat_packet)

if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR)

output_file = os.path.join(OUT_DIR, "satellite_orbits.czml")

# --- 4. 寫入檔案 ---
with open(output_file, 'w') as f:
    json.dump(czml, f, indent=2)

print(f"\n✅ 成功轉換並儲存為 {output_file}")