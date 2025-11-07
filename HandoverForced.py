import argparse
import pandas as pd
import os
from typing import Callable, Dict, List

# --- 1. 模擬參數設定 ---

DEFAULT_INPUT_CSV = os.path.join('output', 'visible_satellites_hsinchu.csv')
DEFAULT_MIN_ELEVATION_DEG = 20.0


# --- 2. Selection strategy functions ---

def select_by_elevation(eligible: pd.DataFrame) -> pd.Series:
    """Return the row of the satellite with max elevation."""
    return eligible.loc[eligible['elevation_deg'].idxmax()]


def select_by_distance(eligible: pd.DataFrame) -> pd.Series:
    """Return the row of the satellite with min distance_km if present,
    otherwise fall back to elevation."""
    if 'distance_km' in eligible.columns:
        return eligible.loc[eligible['distance_km'].idxmin()]
    return select_by_elevation(eligible)


def select_by_service_time(eligible: pd.DataFrame, future_df: pd.DataFrame, current_time, min_elev: float) -> pd.Series:
    """Select the satellite that will remain eligible the longest starting from current_time.

    Args:
        eligible: rows at current_time that are eligible
        future_df: full dataframe sorted by time
        current_time: Timestamp of the current group

    Returns:
        The row (from eligible) whose satellite has the longest continuous run of being eligible
        (elevation > threshold) starting at current_time. If tie or data missing, falls back to distance/elevation.
    """
    # if caller didn't provide future_df/current_time/min_elev, behave as a fallback selector
    if future_df is None or current_time is None or min_elev is None:
        return select_by_distance(eligible)

    candidates = []
    # for each satellite currently eligible, calculate how long it remains eligible in future_df
    for sat in eligible['satellite'].unique():
        # find all rows for this satellite at or after current_time
        sat_rows = future_df[(future_df['satellite'] == sat) & (future_df['time'] >= current_time)]
        # count contiguous rows from the start where elevation stays > min_elev
        duration = 0.0
        sat_rows = sat_rows.sort_values(by='time')
        # find how long (in seconds) the satellite remains continuously > min_elev
        last_valid_time = None
        for _, row in sat_rows.iterrows():
            if row['elevation_deg'] <= min_elev:
                break
            if last_valid_time is None:
                last_valid_time = row['time']
            else:
                last_valid_time = row['time']
        if last_valid_time is not None:
            duration = (last_valid_time - pd.to_datetime(current_time)).total_seconds()
        candidates.append((sat, duration))

    if not candidates:
        # fallback
        return select_by_distance(eligible)

    # pick sat with max duration
    candidates.sort(key=lambda x: (-x[1], x[0]))  # max duration, deterministic tie-break by name
    best_sat = candidates[0][0]
    return eligible[eligible['satellite'] == best_sat].iloc[0]


STRATEGIES: Dict[str, Callable] = {
    'elevation': select_by_elevation,
    'distance': select_by_distance,
    'service_time': select_by_service_time,
    'time': select_by_service_time,
}


def run_handover_forced(input_csv: str = DEFAULT_INPUT_CSV,
                        min_elev_deg: float = DEFAULT_MIN_ELEVATION_DEG,
                        strategy: str = 'distance') -> List[Dict]:
    """Forced-only handover with pluggable selection strategy.

    Args:
        input_csv: path to visibility CSV
        min_elev_deg: elevation threshold
        strategy: one of the keys in STRATEGIES

    Returns:
        List of event dicts (same shape as previous script)
    """
    print(f"--- 開始執行 Forced-only Handover 模擬 (strategy={strategy}) ---")
    print(f"讀取輸入資料: {input_csv}")
    print(f"換手門檻 (Min Elevation): {min_elev_deg}°")
    print("-" * 30)

    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{input_csv}'。")
        return []

    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values(by='time')

    if strategy not in STRATEGIES:
        print(f"❌ 未知策略: {strategy}. 可用: {list(STRATEGIES.keys())}")
        return []

    selector = STRATEGIES[strategy]

    current_sat = None
    handover_events: List[Dict] = []

    grouped = df.groupby('time')
    for t, sats in grouped:
        eligible = sats[sats['elevation_deg'] > min_elev_deg]

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
            continue

        if current_sat is None:
            # service_time strategy needs access to future rows and current time
            if strategy in ('service_time', 'time'):
                best = selector(eligible, df, t, min_elev_deg)
            else:
                best = selector(eligible)
            # reason message uses distance if available
            if 'distance_km' in best.index:
                reason = f'找到第一顆合格衛星 (距離 {best["distance_km"]:.2f} km)'
            else:
                reason = f'找到第一顆合格衛星 (仰角 {best["elevation_deg"]:.2f}°)'

            current_sat = best['satellite']
            handover_events.append({
                'time': t,
                'event': '初始連線 (Initial Acquisition)',
                'from_sat': 'None',
                'to_sat': current_sat,
                'reason': reason
            })
            continue

        cur_rows = sats[sats['satellite'] == current_sat]
        if cur_rows.empty:
            cur_elev = -999
        else:
            cur_elev = cur_rows.iloc[0]['elevation_deg']

        if cur_elev < min_elev_deg:
            if not eligible.empty:
                if strategy in ('service_time', 'time'):
                    best = selector(eligible, df, t, min_elev_deg)
                else:
                    best = selector(eligible)
                if 'distance_km' in best.index and strategy == 'distance':
                    reason = f'原衛星仰角 {cur_elev:.2f}° 過低；選擇距離最近的衛星 (距離 {best["distance_km"]:.2f} km)'
                else:
                    reason = f'原衛星仰角 {cur_elev:.2f}° 過低'

                handover_events.append({
                    'time': t,
                    'event': '強制換手 (Forced HO)',
                    'from_sat': current_sat,
                    'to_sat': best['satellite'],
                    'reason': reason
                })
                current_sat = best['satellite']
            else:
                handover_events.append({
                    'time': t,
                    'event': '連線中斷 (Loss of Connection)',
                    'from_sat': current_sat,
                    'to_sat': 'None',
                    'reason': 'no eligible satellites'
                })
                current_sat = None

    return handover_events


def print_or_save_events(events: List[Dict], out_file: str = None) -> None:
    if not events:
        print("未執行模擬或無事件。")
        return

    if out_file:
        with open(out_file, 'w') as f:
            for event in events:
                f.write(f"[Time]: {event['time']}\n")
                f.write(f"Event: {event['event']}\n")
                f.write(f"From: {event['from_sat']}\n")
                f.write(f"To: {event['to_sat']}\n")
                f.write(f"Reason: {event['reason']}\n\n")
        print(f"已將模擬結果寫入 {out_file}")
    else:
        print("\n--- 模擬結果：Handover 日誌 ---")
        for event in events:
            print(f"\n[Time]: {event['time']}")
            print(f"  Event: {event['event']}")
            print(f"  From:  {event['from_sat']}")
            print(f"  To:    {event['to_sat']}")
            print(f"  Reason: {event['reason']}")
        print("-" * 30)
        print(f"✅ 模擬完成！總共發生 {len(events)} 次事件。")


def _build_cli():
    p = argparse.ArgumentParser(description='Forced-only handover with selectable strategy')
    p.add_argument('--input', '-i', default=DEFAULT_INPUT_CSV)
    p.add_argument('--min-elev', type=float, default=DEFAULT_MIN_ELEVATION_DEG)
    p.add_argument('--strategy', choices=list(STRATEGIES.keys()), default='distance')
    p.add_argument('--out-file', help='optional path to save event log')
    return p


if __name__ == '__main__':
    parser = _build_cli()
    args = parser.parse_args()
    events = run_handover_forced(input_csv=args.input, min_elev_deg=args.min_elev, strategy=args.strategy)
    print_or_save_events(events, out_file=args.out_file)
