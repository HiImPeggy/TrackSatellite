import pandas as pd
import json
from datetime import datetime
import os
import math # 為了傾角 (如果需要)

# --- 1. 設定檔案路徑與模擬參數 ---
INPUT_CSV = os.path.join("output", "visible_satellites_hsinchu.csv")
OUTPUT_CZML = os.path.join("output", "handover_viz.czml")

MIN_ELEVATION_THRESHOLD_DEG = 20.0
HYSTERESIS_MARGIN_DEG = 5.0

# --- 2. 載入與處理資料 ---
print(f"Loading data from {INPUT_CSV}...")
try:
    df = pd.read_csv(INPUT_CSV)
except FileNotFoundError:
    print(f"❌ 錯誤：找不到檔案 '{INPUT_CSV}'。")
    print("請先執行 `skyfield_data_generator.py` (您之前的腳本) 來產生資料。")
    exit()

df['time'] = pd.to_datetime(df['time'])
df = df.sort_values(by='time')

sim_start_time = df['time'].min().isoformat() + "Z"
sim_end_time = df['time'].max().isoformat() + "Z"
all_time_steps = df['time'].unique()

print("Data loaded. Starting Handover simulation for CZML generation...")

# --- 3. 執行「換手演算法」並記錄狀態 ---
ue_connection_log = [] 
current_satellite_name = None

hsinchu_lon = 120.97
hsinchu_lat = 24.8
hsinchu_alt_m = 0 

# 建立一個 satellite_name 到 CZML ID 的映射表 (方便查閱)
sat_name_to_id = {}
for i, name in enumerate(df['satellite'].unique()):
    sat_name_to_id[name] = f"satellite_{i}" 

for time_step in all_time_steps:
    
    satellites_at_this_moment = df[df['time'] == time_step]
    eligible_sats = satellites_at_this_moment[
        satellites_at_this_moment['elevation_deg'] > MIN_ELEVATION_THRESHOLD_DEG
    ]

    new_active_satellite_name = current_satellite_name

    if eligible_sats.empty:
        new_active_satellite_name = None
    else:
        best_overall_sat = eligible_sats.loc[eligible_sats['elevation_deg'].idxmax()]
        
        if current_satellite_name is None:
            new_active_satellite_name = best_overall_sat['satellite']
        else:
            try:
                current_sat_stats = satellites_at_this_moment[
                    satellites_at_this_moment['satellite'] == current_satellite_name
                ].iloc[0]
                current_sat_elevation = current_sat_stats['elevation_deg']
            except IndexError:
                current_sat_elevation = -999 

            if current_sat_elevation < MIN_ELEVATION_THRESHOLD_DEG:
                new_active_satellite_name = best_overall_sat['satellite']
            elif best_overall_sat['elevation_deg'] > current_sat_elevation + HYSTERESIS_MARGIN_DEG:
                new_active_satellite_name = best_overall_sat['satellite']
    
    ue_connection_log.append({
        "time": time_step,
        "connected_sat_name": new_active_satellite_name
    })
    current_satellite_name = new_active_satellite_name

print("Handover simulation complete. Generating CZML...")

# --- 4. CZML 檔案的 "骨架" ---
czml = []

# --- 4a. Document Packet (文件標頭) ---
doc_packet = {
    "id": "document",
    "name": "Handover Simulation in 3D (Hsinchu)",
    "version": "1.0",
    "clock": {
        "interval": f"{sim_start_time}/{sim_end_time}",
        "currentTime": sim_start_time,
        "multiplier": 15,
        "range": "LOOP_STOP"
    }
}
czml.append(doc_packet)

# --- 4b. Hsinchu Location Packet (新竹標示點) ---
hsinchu_packet = {
    "id": "hsinchu",
    "name": "Hsinchu (觀測點)",
    "position": {
        "cartographicDegrees": [hsinchu_lon, hsinchu_lat, hsinchu_alt_m]
    },
    "point": {
        "color": {"rgba": [255, 128, 0, 255]}, 
        "pixelSize": 15
    },
    "label": {
        "text": "Hsinchu (UE)",
        "fillColor": {"rgba": [255, 128, 0, 255]},
        "font": "14pt sans-serif",
        "pixelOffset": {"cartesian2": [0, -20]},
        "show": True
    }
}
czml.append(hsinchu_packet)

# --- 4c. Satellite Packets (所有可見衛星的封包) ---
print(f"Adding {df['satellite'].nunique()} unique satellites to CZML...")
grouped = df.groupby('satellite')
for sat_name, sat_data in grouped:
    position_data = []
    sat_start_time = sat_data['time'].min().isoformat() + "Z"
    sat_end_time = sat_data['time'].max().isoformat() + "Z"
    
    for _, row in sat_data.iterrows():
        time_iso = row['time'].isoformat() + "Z"
        position_data.append(time_iso)
        position_data.append(row['lon_subpoint'])
        position_data.append(row['lat_subpoint'])
        position_data.append(row['height_km'] * 1000) 
        
    sat_czml_id = sat_name_to_id[sat_name]

    sat_packet = {
        "id": sat_czml_id,
        "name": sat_name,
        "availability": f"{sat_start_time}/{sat_end_time}",
        "model": {
            "gltf": "data:application/octet-stream;base64,eyJBTkciOiJUaGlzIGlzIGEgcGxhY2Vob2xkZXIgZm9yIGEgc2F0ZWxsaXRlIG1vZGVsLiJ9",
            "minimumPixelSize": 32,
            "maximumScale": 20000 
        },
        "path": { 
            "material": {
                "solidColor": {
                    "color": {"rgba": [77, 255, 255, 50]} 
                }
            },
            "width": 1,
            "leadTime": 3600, 
            "trailTime": 3600 
        },
        "label": { 
            "text": sat_name,
            "fillColor": {"rgba": [255, 255, 255, 255]},
            "font": "8pt sans-serif",
            "horizontalOrigin": "LEFT",
            "pixelOffset": {"cartesian2": [12, 0]},
        },
        "position": {
            "cartographicDegrees": position_data
        }
    }
    czml.append(sat_packet)

OUT_DIR = "output"

active_satellite_position_ref = [] # 記錄「目標」位置的時間序列
active_satellite_show_bool = []    # 記錄「紅線」是否顯示的時間序列

for entry in ue_connection_log:
    time_iso = entry['time'].isoformat() + "Z"
    
    active_satellite_position_ref.append(time_iso)
    active_satellite_show_bool.append(time_iso)

    if entry['connected_sat_name'] is not None:
        # 有連線：目標的位置 = 衛星的位置
        connected_sat_czml_id = sat_name_to_id[entry['connected_sat_name']]
        active_satellite_position_ref.append({"reference": f"{connected_sat_czml_id}#position"})
        
        # 有連線：紅線 = 顯示
        active_satellite_show_bool.append(True)
    else:
        # 斷線：目標的位置 = 新竹 (這樣線的長度為0，但我們也會隱藏它)
        active_satellite_position_ref.append({"reference": "hsinchu#position"})
        
        # 斷線：紅線 = 隱藏
        active_satellite_show_bool.append(False)

# --- 4e. 建立一個「隱形的目標」實體 ---
# 這東西是隱形的，它的位置會動態切換到 UE 連上的那顆衛星
target_entity_packet = {
    "id": "active_satellite_target",
    "name": "Active Connection Target",
    "availability": f"{sim_start_time}/{sim_end_time}",
    "position": {
        # "position" 屬性會根據 "active_satellite_position_ref" 列表的定義，
        # 在不同時間點去 "參考" 不同衛星的 "position" 屬性
        "reference": active_satellite_position_ref
    },
    "point": { # 保持隱形
        "color": {"rgba": [0, 0, 0, 0]},
        "pixelSize": 0
    }
}
czml.append(target_entity_packet)

# --- 4f. 建立「UE 連線線段」 (紅線) ---
# 這條紅線的起點永遠是「新竹」，終點永遠是「隱形的目標」
ue_connection_packet = {
    "id": "ue_to_sat_connection",
    "name": "UE to Active Satellite Connection",
    "availability": f"{sim_start_time}/{sim_end_time}",
    "polyline": {
        "positions": {
            # 固定的參考點
            "references": [
                "hsinchu#position",
                "active_satellite_target#position"
            ]
        },
        "material": {
            "solidColor": {
                "color": {"rgba": [255, 0, 0, 200]} # 紅色
            }
        },
        "width": 5,
        "clampToGround": False,
        "show": { # 根據 "active_satellite_show_bool" 列表動態顯示或隱藏
            "boolean": active_satellite_show_bool
        }
    }
}
czml.append(ue_connection_packet)
# ▲▲▲▲▲ 修正邏輯結束 ▲▲▲▲▲
# =========================================================================


# --- 5. 寫入檔案 ---
if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR)
    print(f"📁 已建立資料夾: {OUT_DIR}")

output_file = os.path.join(OUT_DIR, "handover_viz.czml")

with open(output_file, 'w') as f:
    json.dump(czml, f, indent=2)

print(f"\n✅ 成功轉換並儲存為 {output_file}")
print("下一步：請使用 'python -m http.server' 啟動伺服器，")
print("然後在瀏覽器中開啟 'http://localhost:8000/index.html'")