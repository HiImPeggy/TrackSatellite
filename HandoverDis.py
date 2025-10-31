import pandas as pd
import os

# --- 1. 模擬參數設定 ---
INPUT_CSV = os.path.join("output", "visible_satellites_hsinchu.csv")

# 最長距離門檻 (只有距離小於此值的衛星才被考慮)
MAX_DISTANCE_THRESHOLD_KM = 2000.0

# 遲滯 (新的衛星必須比目前衛星「更近」這麼多才換手)
HYSTERESIS_MARGIN_KM = 50.0

# 欄位名稱（CSV 必須包含 distance_km）
DIST_COL = "distance_km"
SAT_COL = "satellite"
TIME_COL = "time"

# --- 2. 核心演算法 (以距離為優先，距離越小越好) ---
def run_handover_distance_simulation():
    """
    讀取 CSV 並以「最短距離 + 門檻 + 遲滯」策略模擬換手。
    CSV 必須包含欄位: time, satellite, distance_km
    """
    print("--- 開始執行 Distance-based Handover 模擬 ---")
    print(f"讀取輸入資料: {INPUT_CSV}")
    print(f"距離門檻 (Max Distance): {MAX_DISTANCE_THRESHOLD_KM} km")
    print(f"遲滯 (Hysteresis): {HYSTERESIS_MARGIN_KM} km")
    print("-" * 30)

    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {INPUT_CSV}")
        return

    for col in (TIME_COL, SAT_COL, DIST_COL):
        if col not in df.columns:
            print(f"❌ CSV 缺少必要欄位: {col}")
            return

    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    df = df.sort_values(by=TIME_COL)

    current_sat = None
    handover_events = []

    grouped = df.groupby(TIME_COL)
    for t, sats in grouped:
        eligible = sats[sats[DIST_COL] < MAX_DISTANCE_THRESHOLD_KM]

        if eligible.empty:
            if current_sat is not None:
                handover_events.append({
                    "time": t,
                    "event": "連線中斷 (Loss of Connection)",
                    "from_sat": current_sat,
                    "to_sat": "None",
                    "reason": f"無任何衛星距離 < {MAX_DISTANCE_THRESHOLD_KM} km"
                })
                current_sat = None
            continue

        best = eligible.loc[eligible[DIST_COL].idxmin()]

        if current_sat is None:
            current_sat = best[SAT_COL]
            handover_events.append({
                "time": t,
                "event": "初始連線 (Initial Acquisition)",
                "from_sat": "None",
                "to_sat": current_sat,
                "reason": f"選取最近衛星 (距離 {best[DIST_COL]:.1f} km)"
            })
            continue

        # 取得目前連線衛星距離（如果當前時間點沒有該衛星資料，視為非常遠）
        cur_rows = sats[sats[SAT_COL] == current_sat]
        if cur_rows.empty:
            current_dist = float("inf")
        else:
            current_dist = cur_rows.iloc[0][DIST_COL]

        # 強制換手：目前衛星超過最大距離門檻
        if current_dist > MAX_DISTANCE_THRESHOLD_KM:
            handover_events.append({
                "time": t,
                "event": "強制換手 (Forced HO)",
                "from_sat": current_sat,
                "to_sat": best[SAT_COL],
                "reason": f"目前衛星距離 {current_dist:.1f} km > {MAX_DISTANCE_THRESHOLD_KM} km"
            })
            current_sat = best[SAT_COL]

        # 遲滯換手：新衛星距離比現有衛星近超過遲滯門檻
        elif best[DIST_COL] < current_dist - HYSTERESIS_MARGIN_KM:
            handover_events.append({
                "time": t,
                "event": "遲滯換手 (Hysteresis HO)",
                "from_sat": current_sat,
                "to_sat": best[SAT_COL],
                "reason": f"新衛星距離 {best[DIST_COL]:.1f} km < (原衛星 {current_dist:.1f} km - {HYSTERESIS_MARGIN_KM} km)"
            })
            current_sat = best[SAT_COL]

        # 否則維持連線

    return handover_events


if __name__ == "__main__":
    log = run_handover_distance_simulation()
    if log:
        print("\n--- 模擬結果：Handover 日誌 ---")
        for e in log:
            print(f"\n[Time]: {e['time']}")
            print(f"  Event: {e['event']}")
            print(f"  From:  {e['from_sat']}")
            print(f"  To:    {e['to_sat']}")
            print(f"  Reason: {e['reason']}")
        print("-" * 30)
        print(f"✅ 模擬完成！總共發生 {len(log)} 次事件。")
    else:
        print("未發現任何事件或模擬未執行。")