import pandas as pd
import os
import sys

# --- 1. 模擬參數設定 ---
INPUT_CSV = os.path.join("output", "visible_satellites_hsinchu.csv")

# 最長距離門檻 (只有距離小於此值的衛星才被考慮)
MAX_DISTANCE_THRESHOLD_KM = 2000.0

# 遲滯 (新的衛星必須比目前衛星「更近」這麼多才換手)
HYSTERESIS_MARGIN_KM = 50.0

# 新增：ping-pong 防護窗口（秒），若在此時間內從 A->B 後又要切回 A，則抑制切換
PING_PONG_WINDOW_SEC = 120

# 欄位名稱（CSV 必須包含 distance_km）
DIST_COL = "distance_km"
SAT_COL = "satellite"
TIME_COL = "time"


def run_handover_distance_simulation():
    """
    讀取 CSV 並以「最短距離 + 門檻 + 遲滯 + ping-pong 抑制」策略模擬換手。
    CSV 必須包含欄位: time, satellite, distance_km
    """
    print("--- 開始執行 Distance-based Handover 模擬 (含 Ping-pong 抑制) ---")
    print(f"讀取輸入資料: {INPUT_CSV}")
    print(f"距離門檻 (Max Distance): {MAX_DISTANCE_THRESHOLD_KM} km")
    print(f"遲滯 (Hysteresis): {HYSTERESIS_MARGIN_KM} km")
    print(f"Ping-pong 防護窗口: {PING_PONG_WINDOW_SEC} 秒")
    print("-" * 30)

    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {INPUT_CSV}")
        return []

    # 欄位檢查
    for col in (TIME_COL, SAT_COL, DIST_COL):
        if col not in df.columns:
            print(f"❌ CSV 缺少必要欄位: {col}")
            return []

    # 時間欄位與排序
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    df = df.sort_values(by=TIME_COL)

    current_sat = None
    handover_events = []

    # track last handover to detect immediate flip-back (ping-pong)
    # last_handover: {"time": datetime, "from": sat_name, "to": sat_name}
    last_handover = {"time": None, "from": None, "to": None}

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
        candidate_sat = best[SAT_COL]
        candidate_dist = best[DIST_COL]

        if current_sat is None:
            current_sat = candidate_sat
            handover_events.append({
                "time": t,
                "event": "初始連線 (Initial Acquisition)",
                "from_sat": "None",
                "to_sat": current_sat,
                "reason": f"選取最近衛星 (距離 {candidate_dist:.1f} km)"
            })
            last_handover = {"time": t, "from": "None", "to": current_sat}
            continue

        # 取得目前連線衛星距離（如果當前時間點沒有該衛星資料，視為非常遠）
        cur_rows = sats[sats[SAT_COL] == current_sat]
        if cur_rows.empty:
            current_dist = float("inf")
        else:
            current_dist = cur_rows.iloc[0][DIST_COL]

        # 決策：是否要換手
        will_handover = False
        handover_type = None
        reason = ""

        # 強制換手：目前衛星超過最大距離門檻
        if current_dist > MAX_DISTANCE_THRESHOLD_KM:
            will_handover = True
            handover_type = "強制換手 (Forced HO)"
            reason = f"目前衛星距離 {current_dist:.1f} km > {MAX_DISTANCE_THRESHOLD_KM} km"

        # 遲滯換手：新衛星距離比現有衛星近超過遲滯門檻
        elif candidate_dist < current_dist - HYSTERESIS_MARGIN_KM:
            will_handover = True
            handover_type = "遲滯換手 (Hysteresis HO)"
            reason = f"新衛星距離 {candidate_dist:.1f} km < (原衛星 {current_dist:.1f} km - {HYSTERESIS_MARGIN_KM} km)"

        if will_handover:
            # 檢查是否為 ping-pong（上一次換手是 candidate -> current，且在窗口內）
            is_pingpong = False
            if last_handover["time"] is not None and last_handover["from"] is not None:
                delta = (t - last_handover["time"]).total_seconds()
                if (last_handover["from"] == candidate_sat and
                        last_handover["to"] == current_sat and
                        delta <= PING_PONG_WINDOW_SEC):
                    is_pingpong = True

            if is_pingpong:
                # 抑制此次換手（避免 ping-pong），並做紀錄
                handover_events.append({
                    "time": t,
                    "event": "抑制換手 (Suppressed HO - Ping-pong prevented)",
                    "from_sat": current_sat,
                    "to_sat": candidate_sat,
                    "reason": (f"檢測到先前從 {candidate_sat} -> {current_sat} 在 {int(delta)}s 內發生，"
                               "抑制回切。")
                })
                # 不更新 current_sat 或 last_handover
                continue

            # 執行換手
            prev_sat = current_sat
            current_sat = candidate_sat
            handover_events.append({
                "time": t,
                "event": handover_type,
                "from_sat": prev_sat,
                "to_sat": current_sat,
                "reason": reason
            })
            last_handover = {"time": t, "from": prev_sat, "to": current_sat}

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