import pandas as pd
import os
from datetime import timedelta

# Input CSV (same as HandoverTest.py use)
INPUT_CSV = os.path.join('output', 'visible_satellites_hsinchu.csv')

MIN_ELEVATION_THRESHOLD_DEG = 20.0
HYSTERESIS_MARGIN_DEG = 5.0
# fixed service hold time (seconds) - not parameterized per your request
SERVICE_HOLD_SECONDS = 120


def run_handover_simulation_service():
    """Service-time based handover but same interface/print format as HandoverTest.py
    This function does not accept parameters; SERVICE_HOLD_SECONDS is used internally.
    """
    print("--- 開始執行 Service-time Handover 模擬 (固定保持時間) ---")
    print(f"讀取輸入資料: {INPUT_CSV}")
    print(f"換手門檻 (Min Elevation): {MIN_ELEVATION_THRESHOLD_DEG}°")
    print(f"換手遲滯 (Hysteresis): {HYSTERESIS_MARGIN_DEG}°")
    print(f"最短保持時間 (秒): {SERVICE_HOLD_SECONDS}")
    print("-" * 30)

    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{INPUT_CSV}'。")
        return []

    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values(by='time')

    current_sat = None
    current_since = None
    handover_events = []

    grouped = df.groupby('time')
    for t, sats in grouped:
        eligible = sats[sats['elevation_deg'] > MIN_ELEVATION_THRESHOLD_DEG]
        if eligible.empty:
            if current_sat is not None:
                handover_events.append({
                    'time': t,
                    'event': '連線中斷 (Loss of Connection)',
                    'from_sat': current_sat,
                    'to_sat': 'None',
                    'reason': 'no eligible satellites'
                })
                current_sat = None
                current_since = None
            continue

        best = eligible.loc[eligible['elevation_deg'].idxmax()]
        if current_sat is None:
            current_sat = best['satellite']
            current_since = t
            handover_events.append({
                'time': t,
                'event': '初始連線 (Initial Acquisition)',
                'from_sat': 'None',
                'to_sat': current_sat,
                'reason': f'找到第一顆合格衛星 (仰角 {best["elevation_deg"]:.2f}°)'
            })
            continue

        # get current elevation
        currows = sats[sats['satellite'] == current_sat]
        if currows.empty:
            cur_elev = -999
        else:
            cur_elev = currows.iloc[0]['elevation_deg']

        # forced HO
        if cur_elev < MIN_ELEVATION_THRESHOLD_DEG:
            handover_events.append({
                'time': t,
                'event': '強制換手 (Forced HO)',
                'from_sat': current_sat,
                'to_sat': best['satellite'],
                'reason': f'原衛星仰角 {cur_elev:.2f}° 過低'
            })
            current_sat = best['satellite']
            current_since = t
            continue

        # hold-time check
        if current_since is not None and (t - current_since) < timedelta(seconds=SERVICE_HOLD_SECONDS):
            continue

        # hysteresis
        if best['elevation_deg'] > cur_elev + HYSTERESIS_MARGIN_DEG:
            handover_events.append({
                'time': t,
                'event': '遲滯換手 (Hysteresis HO)',
                'from_sat': current_sat,
                'to_sat': best['satellite'],
                'reason': f'新衛星仰角 {best["elevation_deg"]:.2f}° > (原衛星 {cur_elev:.2f}° + {HYSTERESIS_MARGIN_DEG}°)'
            })
            current_sat = best['satellite']
            current_since = t

    return handover_events


if __name__ == '__main__':
    ho_log = run_handover_simulation_service()
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
