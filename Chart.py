from cmath import log10
import numpy as np
import math
from cmath import log10
import numpy as np
import math
import os
import re
import matplotlib.pyplot as plt
from collections import defaultdict
from collections import Counter
from datetime import datetime

EVENT_FILES = [
    os.path.join("output", "events", "5.txt"),
    os.path.join("output", "events", "1.txt"),
    os.path.join("output", "events", "4.txt"),
    os.path.join("output", "events", "2.txt"),
    os.path.join("output", "events", "3.txt"),
    os.path.join("output", "events", "6.txt")
]

X_ALIASES = {
    "1.txt": "Elevation5",
    "2.txt": "Distance",
    "3.txt": "PingPong",
    "4.txt": "Elevation30",
    "5.txt": "BHO",
    "6.txt": "Service Time"
}

# simple top-level parameter: change this value to change frequency bin size (seconds)
BIN_SECONDS = 120

EVENT_KEYWORDS = {
    "initial": ["Initial Acquisition"],
    "hysteresis": ["Hysteresis HO"],
    "forced": ["Forced HO"],
    "loss": ["Loss of Connection"],
    "suppressed": ["Suppressed HO",],
}


def parse_event_file(path):
    """Return a dict of counts per event-type for the given file."""
    counts = defaultdict(int)
    if not os.path.isfile(path):
        return counts

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # try to extract an explicit total if present: "總共發生 116 次事件"
    explicit_total = None
    m = re.search(r"總共發生\s*([0-9]+)\s*次事件", content)
    if m:
        explicit_total = int(m.group(1))
        counts["total"] = explicit_total

    # Count occurrences of each event keyword
    for key, keywords in EVENT_KEYWORDS.items():
        for kw in keywords:
            counts[key] += content.count(kw)

    # If we have zero for everything, fallback to counting event blocks like '[Time]:'
    if not any(counts[k] for k in counts if k != "total"):
        counts.clear()
        counts["total"] = len(re.findall(r"^\[Time\]:", content, flags=re.MULTILINE))

    # Ensure total exists; use breakdown sum only if explicit total not provided
    breakdown_sum = sum(v for k, v in counts.items() if k != "total")
    if breakdown_sum > 0 and explicit_total is None:
        counts["total"] = breakdown_sum

    return counts


def make_plots(file_paths):
    labels = [X_ALIASES.get(os.path.basename(p), os.path.basename(p)) for p in file_paths]
    per_file_counts = [parse_event_file(p) for p in file_paths]

    totals = [c.get("total", 0) for c in per_file_counts]

    # Prepare stacked breakdown for known event types (consistent order)
    event_types = ["initial", "hysteresis", "forced", "loss", "suppressed"]
    breakdown = {et: [c.get(et, 0) for c in per_file_counts] for et in event_types}

    out_dir = os.path.join("output", "plots")
    os.makedirs(out_dir, exist_ok=True)

    # Plot 1: total counts per file (narrower bars)
    out_total = os.path.join(out_dir, "handover_counts.png")
    fig, ax = plt.subplots(figsize=(6, 4))
    x = list(range(len(labels)))
    width = 0.35
    bars = ax.bar(x, totals, width=width, color=["#c44e52", "#f59127", "#e7b800", "#55a868", "#4c72b0", "#8172b2"]) 
    ax.set_title("Handover event counts (total)")
    ax.set_ylabel("Count")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, max(totals) * 1.25 if totals and max(totals) > 0 else 1)
    for bar, c in zip(bars, totals):
        ax.text(bar.get_x() + bar.get_width() / 2, c + 0.5, str(c), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(out_total, dpi=150)
    plt.close(fig)

    # Plot 2: stacked breakdown per event type
    out_stack = os.path.join(out_dir, "handover_breakdown.png")
    fig, ax = plt.subplots(figsize=(8, 4))
    bottom = [0] * len(labels)
    colors = {"initial": "#4c72b0", "hysteresis": "#55a868", "forced": "#c44e52", "loss": "#8172b2", "suppressed": "#e7b800"}
    x = list(range(len(labels)))
    width = 0.35
    for et in event_types:
        vals = breakdown[et]
        ax.bar(x, vals, width=width, bottom=bottom, label=et, color=colors.get(et))
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)

    ax.set_title("Handover event breakdown by type")
    ax.set_ylabel("Count")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_stack, dpi=150)
    plt.close(fig)

    return {
        "total_plot": out_total,
        "breakdown_plot": out_stack,
        "labels": labels,
        "totals": totals,
        "per_file_counts": per_file_counts,
    }


def parse_event_times(path):
    """Extract event timestamps (datetime objects) from a simulator event file.
    Lines are expected to contain a timestamp after '[Time]: '."""
    times = []
    if not os.path.isfile(path):
        return times
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("[Time]:"):
                # format: [Time]: 2025-10-31 10:54:29
                parts = line.split("[Time]:", 1)[1].strip()
                try:
                    dt = datetime.strptime(parts, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    # try alternative parse
                    try:
                        dt = datetime.fromisoformat(parts)
                    except Exception:
                        continue
                times.append(dt)
    return times


def plot_frequency(file_paths, out_dir="output/plots", bin_seconds=60):
    """Plot event frequency (events per bin_seconds) for each file and save PNG."""
    os.makedirs(out_dir, exist_ok=True)
    series = []
    labels = []
    for p in file_paths:
        times = parse_event_times(p)
        labels = [X_ALIASES.get(os.path.basename(p), os.path.basename(p)) for p in file_paths]
        if not times:
            series.append(([], []))
            continue
        # bin by minute (or bin_seconds)
        # convert to epoch seconds then floor to bin
        bins = Counter()
        for dt in times:
            key = int(dt.timestamp()) // bin_seconds * bin_seconds
            bins[key] += 1
        # create sorted lists
        xs = sorted(bins.keys())
        ys = [bins[x] for x in xs]
        # convert xs back to datetimes for plotting
        xdt = [datetime.fromtimestamp(x) for x in xs]
        series.append((xdt, ys))

    # plot per-file time series on same axes
    out_png = os.path.join(out_dir, "handover_frequency.png")
    fig, ax = plt.subplots(figsize=(10, 4))
    for (xdt, ys), lab in zip(series, labels):
        if not xdt:
            continue
        ax.plot(xdt, ys, marker="o", label=lab)
    ax.set_title(f"Handover frequency (events per {bin_seconds}s)")
    ax.set_ylabel("Events per bin")
    ax.legend()
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


def main():
    results = make_plots(EVENT_FILES)
    print(f"Saved total plot: {results['total_plot']}")
    print(f"Saved breakdown plot: {results['breakdown_plot']}")
    print("\nCounts per file:")
    for label, counts in zip(results["labels"], results["per_file_counts"]):
        print(f"  {label}:")
        for k, v in counts.items():
            print(f"    {k}: {v}")

    # generate and report frequency plot (uses BIN_SECONDS)
    freq_png = plot_frequency(EVENT_FILES, out_dir=os.path.join("output", "plots"), bin_seconds=BIN_SECONDS)
    print(f"Saved frequency plot: {freq_png}")


if __name__ == "__main__":
    main()