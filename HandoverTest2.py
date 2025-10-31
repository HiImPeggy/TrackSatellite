import pandas as pd
import os

# --- 1. 模擬參數設定 ---

INPUT_CSV = os.path.join("output", "visible_satellites_hsinchu.csv")

# 門檻 (Threshold)：衛星必須高於這個仰角才會被考慮
MIN_ELEVATION_THRESHOLD_DEG = 20.0

# 遲滯 (Hysteresis)：新的衛星必須比舊的衛星好「這麼多」，才值得換手
HYSTERESIS_MARGIN_DEG = 30.0

# --- 2. 核心演算法 ---

def run_handover_simulation():
    """
    讀取 CSV 檔案並執行「具備遲滯與門檻的最佳仰角」HO 演算法
    """
    
    print("--- 開始執行 Handover 模擬 ---")
    print(f"讀取輸入資料: {INPUT_CSV}")
    print(f"換手門檻 (Min Elevation): {MIN_ELEVATION_THRESHOLD_DEG}°")
    print(f"換手遲滯 (Hysteresis): {HYSTERESIS_MARGIN_DEG}°")
    print("-" * 30)
    
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{INPUT_CSV}'。")
        print("請先執行 `skyfield_data_generator.py` (您之前的腳本) 來產生資料。")
        return

    # 將 'time' 欄位轉換為 datetime 物件，並依此排序
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values(by='time')

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

        # 3. 找出「整體最佳」的衛星
        best_overall_sat = eligible_sats.loc[eligible_sats['elevation_deg'].idxmax()]

        # 4. 決策：Case 1 -「初始連線」
        if current_satellite_name is None:
            current_satellite_name = best_overall_sat['satellite']
            handover_events.append({
                "time": time_step,
                "event": "初始連線 (Initial Acquisition)",
                "from_sat": "None",
                "to_sat": current_satellite_name,
                "reason": f"找到第一顆合格衛星 (仰角 {best_overall_sat['elevation_deg']:.2f}°)"
            })
            continue

        # 5. 決策：Case 2 -「維持連線」
        
        # 取得目前連線衛星的即時數據
        try:
            current_sat_stats = satellites_at_this_moment[
                satellites_at_this_moment['satellite'] == current_satellite_name
            ].iloc[0]
            current_sat_elevation = current_sat_stats['elevation_deg']
        except IndexError:
            # 這情況很少見，但可能發生 (e.g. CSV 資料不連續)
            current_sat_elevation = -999 # 設為一個極小值

        # 5a. 檢查「強制換手」(目前連線的衛星掉到門檻下了)
        if current_sat_elevation < MIN_ELEVATION_THRESHOLD_DEG:
            handover_events.append({
                "time": time_step,
                "event": "強制換手 (Forced HO)",
                "from_sat": current_satellite_name,
                "to_sat": best_overall_sat['satellite'],
                "reason": f"原衛星仰角 {current_sat_elevation:.2f}° 過低 (<{MIN_ELEVATION_THRESHOLD_DEG}°)"
            })
            current_satellite_name = best_overall_sat['satellite']
            
        # 5b. 檢查「遲滯換手」(出現了「明顯更好」的選擇)
        elif best_overall_sat['elevation_deg'] > current_sat_elevation + HYSTERESIS_MARGIN_DEG:
            handover_events.append({
                "time": time_step,
                "event": "遲滯換手 (Hysteresis HO)",
                "from_sat": current_satellite_name,
                "to_sat": best_overall_sat['satellite'],
                "reason": f"新衛星仰角 {best_overall_sat['elevation_deg']:.2f}° > (原衛星 {current_sat_elevation:.2f}° + {HYSTERESIS_MARGIN_DEG}°)"
            })
            current_satellite_name = best_overall_sat['satellite']
        
        # 5c. 維持不變 (Else)
        # (不需要做任何事，繼續連線 current_satellite_name)
        
    return handover_events

# --- 3. 執行與顯示結果 ---
if __name__ == "__main__":
    
    # 執行模擬
    ho_log = run_handover_simulation()
    
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
    else:
        print("未執行模擬 (可能找不到輸入檔案)。")