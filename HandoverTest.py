import pandas as pd
import os
import numpy as np
import csv

# --- 1. 模擬參數設定 ---

INPUT_CSV = os.path.join("output", "visible_satellites_hsinchu.csv")
OUT_DIR = "output"

# 門檻 (Threshold)：衛星必須高於這個仰角才會被考慮
MIN_ELEVATION_THRESHOLD_DEG = 20.0

# 遲滯 (Hysteresis)：新的衛星必須比舊的衛星近「這麼多」公里，才值得換手
HYSTERESIS_MARGIN_KM = 100.0  # 使用距離作為遲滯標準

# 新竹的地心座標 (ECEF)，單位：公里
# 經緯度: (24.8°N, 120.97°E)
HSINCHU_LAT = 24.8
HSINCHU_LON = 120.97
HSINCHU_ALT_KM = 0.0  # 海拔高度（公里）

def latlon_to_ecef(lat_deg, lon_deg, alt_km):
    """
    將經緯度座標轉換為地心座標 (ECEF)
    使用 WGS84 橢球模型
    """
    # WGS84 參數
    a = 6378.137  # 長半軸 (km)
    f = 1 / 298.257223563  # 扁率
    e2 = 2 * f - f * f  # 第一偏心率平方
    
    lat_rad = np.radians(lat_deg)
    lon_rad = np.radians(lon_deg)
    
    # 卯酉圈曲率半徑
    N = a / np.sqrt(1 - e2 * np.sin(lat_rad)**2)
    
    x = (N + alt_km) * np.cos(lat_rad) * np.cos(lon_rad)
    y = (N + alt_km) * np.cos(lat_rad) * np.sin(lon_rad)
    z = (N * (1 - e2) + alt_km) * np.sin(lat_rad)
    
    return x, y, z

# 計算新竹的地心座標
HSINCHU_X, HSINCHU_Y, HSINCHU_Z = latlon_to_ecef(HSINCHU_LAT, HSINCHU_LON, HSINCHU_ALT_KM)

# --- 2. 核心演算法 ---

def calculate_ecef_distance(sat_x, sat_y, sat_z):
    """
    計算衛星與新竹觀測點在地心座標系統下的距離
    """
    dx = sat_x - HSINCHU_X
    dy = sat_y - HSINCHU_Y
    dz = sat_z - HSINCHU_Z
    return np.sqrt(dx**2 + dy**2 + dz**2)

def run_handover_simulation():
    """
    讀取 CSV 檔案並執行「基於地心座標距離的換手」HO 演算法
    使用 ECEF 座標計算衛星與地面站的實際距離
    """
    
    print("--- 開始執行 Handover 模擬 (基於地心座標) ---")
    print(f"讀取輸入資料: {INPUT_CSV}")
    print(f"換手門檻 (Min Elevation): {MIN_ELEVATION_THRESHOLD_DEG}°")
    print(f"換手遲滯 (Hysteresis): {HYSTERESIS_MARGIN_KM} km (距離)")
    print(f"新竹地心座標 (ECEF): X={HSINCHU_X:.2f}, Y={HSINCHU_Y:.2f}, Z={HSINCHU_Z:.2f} km")
    print("-" * 30)
    
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{INPUT_CSV}'。")
        print("請先執行 `SatTrack.py` 來產生資料。")
        return

    # 將 'time' 欄位轉換為 datetime 物件，並依此排序
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values(by='time')
    
    # 計算每顆衛星與新竹的 ECEF 距離
    df['ecef_distance_km'] = calculate_ecef_distance(
        df['x_ecef_km'].values,
        df['y_ecef_km'].values,
        df['z_ecef_km'].values
    )

    # 狀態變數
    current_satellite_name = None
    handover_events = [] # 我們的日誌

    # 依據「時間點」將資料分組，模擬時間的推進
    grouped_by_time = df.groupby('time')

    for time_step, satellites_at_this_moment in grouped_by_time:
        
        # 1. 篩選：只找出「高於」門檻的合格衛星
        eligible_sats = satellites_at_this_moment[
            satellites_at_this_moment['elevation_deg'] > MIN_ELEVATION_THRESHOLD_DEG
        ]

        # 2. 如果該時間點「沒有任何」合格衛星
        if eligible_sats.empty:
            if current_satellite_name is not None:
                # 我們失去了唯一的連線
                handover_events.append({
                    "time": time_step,
                    "event": "連線中斷 (Loss of Connection)",
                    "from_sat": current_satellite_name,
                    "to_sat": "None",
                    "reason": f"原衛星 {current_satellite_name} 訊號低於門檻，且無其他合格衛星。"
                })
                current_satellite_name = None
            continue # 進入下一個時間點

        # 3. 找出「整體最佳」的衛星 (距離最近的)
        best_overall_sat = eligible_sats.loc[eligible_sats['ecef_distance_km'].idxmin()]

        # 4. 決策：Case 1 -「初始連線」
        if current_satellite_name is None:
            current_satellite_name = best_overall_sat['satellite']
            handover_events.append({
                "time": time_step,
                "event": "初始連線 (Initial Acquisition)",
                "from_sat": "None",
                "to_sat": current_satellite_name,
                "reason": f"找到第一顆合格衛星 (ECEF距離 {best_overall_sat['ecef_distance_km']:.2f} km, 仰角 {best_overall_sat['elevation_deg']:.2f}°)"
            })
            continue

        # 5. 決策：Case 2 -「維持連線」
        
        # 取得目前連線衛星的即時數據
        try:
            current_sat_stats = satellites_at_this_moment[
                satellites_at_this_moment['satellite'] == current_satellite_name
            ].iloc[0]
            current_sat_elevation = current_sat_stats['elevation_deg']
            current_sat_distance = current_sat_stats['ecef_distance_km']
        except IndexError:
            # 這情況很少見，但可能發生 (e.g. CSV 資料不連續)
            current_sat_elevation = -999 # 設為一個極小值
            current_sat_distance = 99999 # 設為一個極大值

        # 5a. 檢查「強制換手」(目前連線的衛星掉到門檻下了)
        if current_sat_elevation < MIN_ELEVATION_THRESHOLD_DEG:
            handover_events.append({
                "time": time_step,
                "event": "強制換手 (Forced HO)",
                "from_sat": current_satellite_name,
                "to_sat": best_overall_sat['satellite'],
                "reason": f"原衛星仰角 {current_sat_elevation:.2f}° 過低 (<{MIN_ELEVATION_THRESHOLD_DEG}°), 切換至距離 {best_overall_sat['ecef_distance_km']:.2f} km 的衛星"
            })
            current_satellite_name = best_overall_sat['satellite']
            
        # 5b. 檢查「遲滯換手」(出現了「明顯更近」的選擇，基於 ECEF 距離)
        elif current_sat_distance - best_overall_sat['ecef_distance_km'] > HYSTERESIS_MARGIN_KM:
            handover_events.append({
                "time": time_step,
                "event": "遲滯換手 (Hysteresis HO - ECEF Distance)",
                "from_sat": current_satellite_name,
                "to_sat": best_overall_sat['satellite'],
                "reason": f"新衛星距離 {best_overall_sat['ecef_distance_km']:.2f} km < (原衛星 {current_sat_distance:.2f} km - {HYSTERESIS_MARGIN_KM} km)"
            })
            current_satellite_name = best_overall_sat['satellite']
        
        # 5c. 維持不變 (Else)
        # (不需要做任何事，繼續連線 current_satellite_name)
    
    # 回傳 handover 日誌，以及輸入資料的起始時間 (用來轉換為相對秒數)
    start_time = df['time'].min()
    return handover_events, start_time

# --- 3. 執行與顯示結果 ---
if __name__ == "__main__":
    
    # 執行模擬，並取得起始時間
    result = run_handover_simulation()
    if not result:
        print("未執行模擬 (可能找不到輸入檔案)。")
    else:
        ho_log, start_time = result
        
        # 顯示結果
        if ho_log:
            print("\n--- 模擬結果：Handover 日誌 ---")
            for event in ho_log:
                print(f"\n[Time]: {event['time']}")
                print(f"  Event: {event['event']}")
                print(f"  From:  {event['from_sat']}")
                print(f"  To:    {event['to_sat']}")
                print(f"  Reason: {event['reason']}")
            
            print("-" * 30)
            print(f"✅ 模擬完成！總共發生 {len(ho_log)} 次事件。")
            
            # 將最終 handover trace 存成 output/handover_trace.csv
            try:
                # 建立目錄（若已存在則不會拋錯）
                os.makedirs(OUT_DIR, exist_ok=True)
                
                output_file = os.path.join(OUT_DIR, "handover_trace.csv")
                
                with open(output_file, "w", newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Time_sec", "From_Sat", "To_Sat"])
                    for event in ho_log:
                        # 將時間轉為相對於起始時間的秒數
                        delta = (event['time'] - start_time).total_seconds()
                        writer.writerow([f"{delta:.1f}", event['from_sat'], event['to_sat']])
                
                print(f"📄 handover trace 已儲存為: {output_file}")
            except Exception as e:
                print(f"❌ 寫入 {output_file} 時發生錯誤: {e}")
        else:
            print("模擬執行但未產生任何 handover 事件。")