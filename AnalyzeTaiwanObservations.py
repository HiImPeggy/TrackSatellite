import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
import os

# Set matplotlib style for better-looking plots
plt.style.use('seaborn-v0_8-darkgrid')

# === 1. Load the data ===
input_file = "output/visible_satellites_taiwan_full.csv"

if not os.path.exists(input_file):
    print(f"❌ Error: {input_file} not found. Please run SatTrackTaiwan.py first.")
    exit(1)

print(f"📂 Loading data from {input_file}...")
df = pd.read_csv(input_file)
print(f"✅ Loaded {len(df)} observation records")
print(f"   - Time range: {df['time'].min()} to {df['time'].max()}")
print(f"   - Unique satellites: {df['satellite'].nunique()}")
print(f"   - Observation points: {df['observer_location'].nunique()}")

# === 2. Analysis 1: How many observation points can see each satellite? ===
print("\n" + "="*80)
print("📊 Analysis 1: Multi-Point Observation of Satellites")
print("="*80)

# Group by time and satellite, count unique observers
satellite_observers = df.groupby(['time', 'satellite'])['observer_location'].nunique().reset_index()
satellite_observers.columns = ['time', 'satellite', 'num_observers']

# Statistics
print(f"\nStatistics on number of observation points per satellite (at each time):")
print(satellite_observers['num_observers'].describe())

# Count how many times satellites are seen by N observation points
observer_count_distribution = satellite_observers['num_observers'].value_counts().sort_index()
print(f"\nDistribution of observation point counts:")
for n_obs, count in observer_count_distribution.items():
    probability = count / len(satellite_observers) * 100
    print(f"  {n_obs} observation point(s): {count} occurrences ({probability:.2f}%)")

# Calculate probability that a satellite is seen by multiple observation points
multi_observer_prob = (satellite_observers['num_observers'] > 1).sum() / len(satellite_observers) * 100
print(f"\n🎯 Probability that a satellite is observed by multiple observation points: {multi_observer_prob:.2f}%")

# === 3. Analysis 2: How many satellites can each observation point see? ===
print("\n" + "="*80)
print("📊 Analysis 2: Multi-Satellite Observation from Each Point")
print("="*80)

# Group by time and observer, count unique satellites
observer_satellites = df.groupby(['time', 'observer_location'])['satellite'].nunique().reset_index()
observer_satellites.columns = ['time', 'observer_location', 'num_satellites']

# Statistics
print(f"\nStatistics on number of satellites per observation point (at each time):")
print(observer_satellites['num_satellites'].describe())

# Count how many times observation points see N satellites simultaneously
satellite_count_distribution = observer_satellites['num_satellites'].value_counts().sort_index()
print(f"\nDistribution of simultaneous satellite counts:")
for n_sats, count in satellite_count_distribution.items():
    probability = count / len(observer_satellites) * 100
    print(f"  {n_sats} satellite(s): {count} occurrences ({probability:.2f}%)")

# Calculate probability of seeing multiple satellites
multi_satellite_prob = (observer_satellites['num_satellites'] > 1).sum() / len(observer_satellites) * 100
print(f"\n🎯 Probability that an observation point sees multiple satellites: {multi_satellite_prob:.2f}%")

# Find the maximum and average
max_simultaneous = observer_satellites.groupby('observer_location')['num_satellites'].max()
avg_simultaneous = observer_satellites.groupby('observer_location')['num_satellites'].mean()

print(f"\n📍 Per observation point statistics:")
for location in sorted(max_simultaneous.index):
    print(f"  {location:15s}: Max={max_simultaneous[location]:2d} satellites, Avg={avg_simultaneous[location]:.2f} satellites")

# === 4. Create Visualizations ===
print("\n" + "="*80)
print("📈 Generating visualizations...")
print("="*80)

# Create output directory for plots
plot_dir = "output/plots"
os.makedirs(plot_dir, exist_ok=True)

# Figure 1: Distribution of observation points per satellite
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Taiwan Satellite Observation Analysis', fontsize=16, fontweight='bold')

# Plot 1a: Histogram of observation points per satellite
ax1 = axes[0, 0]
ax1.bar(observer_count_distribution.index, observer_count_distribution.values, 
        color='steelblue', edgecolor='black', alpha=0.7)
ax1.set_xlabel('Number of Observation Points', fontsize=11)
ax1.set_ylabel('Frequency (count)', fontsize=11)
ax1.set_title('Distribution: How Many Points Can See Each Satellite?', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
# Add percentage labels on bars
for x, y in zip(observer_count_distribution.index, observer_count_distribution.values):
    pct = y / len(satellite_observers) * 100
    ax1.text(x, y, f'{pct:.1f}%', ha='center', va='bottom', fontsize=9)

# Plot 1b: Box plot of observation points per satellite
ax2 = axes[0, 1]
ax2.boxplot([satellite_observers['num_observers']], labels=['All Satellites'])
ax2.set_ylabel('Number of Observation Points', fontsize=11)
ax2.set_title('Box Plot: Observation Points per Satellite', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')

# Plot 2a: Histogram of satellites per observation point
ax3 = axes[1, 0]
ax3.bar(satellite_count_distribution.index, satellite_count_distribution.values,
        color='coral', edgecolor='black', alpha=0.7)
ax3.set_xlabel('Number of Satellites', fontsize=11)
ax3.set_ylabel('Frequency (count)', fontsize=11)
ax3.set_title('Distribution: How Many Satellites Per Observation Point?', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)
# Add percentage labels on bars
for x, y in zip(satellite_count_distribution.index, satellite_count_distribution.values):
    pct = y / len(observer_satellites) * 100
    ax3.text(x, y, f'{pct:.1f}%', ha='center', va='bottom', fontsize=9)

# Plot 2b: Bar chart of average satellites per location
ax4 = axes[1, 1]
locations_sorted = avg_simultaneous.sort_values(ascending=False)
bars = ax4.barh(range(len(locations_sorted)), locations_sorted.values, 
                color='lightseagreen', edgecolor='black', alpha=0.7)
ax4.set_yticks(range(len(locations_sorted)))
ax4.set_yticklabels(locations_sorted.index, fontsize=9)
ax4.set_xlabel('Average Number of Satellites', fontsize=11)
ax4.set_title('Average Satellites Visible per Location', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3, axis='x')
# Add value labels
for i, v in enumerate(locations_sorted.values):
    ax4.text(v, i, f'{v:.1f}', va='center', ha='left', fontsize=8, color='black')

plt.tight_layout()
output_file_1 = os.path.join(plot_dir, "taiwan_observation_distribution.png")
plt.savefig(output_file_1, dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_file_1}")

# Figure 2: Time series analysis
fig2, axes2 = plt.subplots(2, 1, figsize=(16, 10))
fig2.suptitle('Taiwan Satellite Observation Over Time', fontsize=16, fontweight='bold')

# Plot 3a: Time series of unique satellites per minute (aggregated across all observers)
satellites_per_time = df.groupby('time')['satellite'].nunique().reset_index()
satellites_per_time.columns = ['time', 'unique_satellites']

ax5 = axes2[0]
ax5.plot(range(len(satellites_per_time)), satellites_per_time['unique_satellites'], 
         color='darkblue', linewidth=2, marker='o', markersize=3)
ax5.set_xlabel('Time Index (minutes)', fontsize=11)
ax5.set_ylabel('Number of Unique Satellites', fontsize=11)
ax5.set_title('Unique Satellites Visible Across All Taiwan (per minute)', fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)
ax5.fill_between(range(len(satellites_per_time)), satellites_per_time['unique_satellites'], 
                  alpha=0.3, color='lightblue')

# Plot 3b: Heatmap-style view of satellites per location over time
# Sample every 10 minutes to make it readable
time_points = sorted(df['time'].unique())
sample_times = time_points[::10]  # Every 10 minutes

heatmap_data = []
locations_list = sorted(df['observer_location'].unique())

for time in sample_times:
    row = []
    for location in locations_list:
        count = len(df[(df['time'] == time) & (df['observer_location'] == location)])
        row.append(count)
    heatmap_data.append(row)

heatmap_array = np.array(heatmap_data).T

ax6 = axes2[1]
im = ax6.imshow(heatmap_array, aspect='auto', cmap='YlOrRd', interpolation='nearest')
ax6.set_yticks(range(len(locations_list)))
ax6.set_yticklabels(locations_list, fontsize=9)
ax6.set_xlabel('Time Index (every 10 minutes)', fontsize=11)
ax6.set_ylabel('Observation Location', fontsize=11)
ax6.set_title('Heatmap: Number of Satellites per Location Over Time', fontsize=12, fontweight='bold')
plt.colorbar(im, ax=ax6, label='Number of Satellites')

plt.tight_layout()
output_file_2 = os.path.join(plot_dir, "taiwan_observation_timeline.png")
plt.savefig(output_file_2, dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_file_2}")

# Figure 3: Detailed probability analysis
fig3, axes3 = plt.subplots(1, 2, figsize=(16, 6))
fig3.suptitle('Multi-Observation Probability Analysis', fontsize=16, fontweight='bold')

# Plot 4a: Cumulative distribution of observation points per satellite
ax7 = axes3[0]
cumulative_obs = []
for i in sorted(observer_count_distribution.index):
    cumulative_obs.append(observer_count_distribution[observer_count_distribution.index <= i].sum())
cumulative_pct = [x / len(satellite_observers) * 100 for x in cumulative_obs]

ax7.plot(sorted(observer_count_distribution.index), cumulative_pct, 
         marker='o', markersize=8, linewidth=2, color='darkgreen')
ax7.set_xlabel('Number of Observation Points', fontsize=11)
ax7.set_ylabel('Cumulative Probability (%)', fontsize=11)
ax7.set_title('CDF: Satellites Observed by N or Fewer Points', fontsize=12, fontweight='bold')
ax7.grid(True, alpha=0.3)
ax7.set_ylim([0, 105])
# Add horizontal line at 50%
ax7.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50th percentile')
ax7.legend()

# Plot 4b: Cumulative distribution of satellites per observation point
ax8 = axes3[1]
cumulative_sats = []
for i in sorted(satellite_count_distribution.index):
    cumulative_sats.append(satellite_count_distribution[satellite_count_distribution.index <= i].sum())
cumulative_pct_sats = [x / len(observer_satellites) * 100 for x in cumulative_sats]

ax8.plot(sorted(satellite_count_distribution.index), cumulative_pct_sats,
         marker='s', markersize=8, linewidth=2, color='darkorange')
ax8.set_xlabel('Number of Satellites', fontsize=11)
ax8.set_ylabel('Cumulative Probability (%)', fontsize=11)
ax8.set_title('CDF: Observation Points Seeing N or Fewer Satellites', fontsize=12, fontweight='bold')
ax8.grid(True, alpha=0.3)
ax8.set_ylim([0, 105])
# Add horizontal line at 50%
ax8.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50th percentile')
ax8.legend()

plt.tight_layout()
output_file_3 = os.path.join(plot_dir, "taiwan_observation_probability.png")
plt.savefig(output_file_3, dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_file_3}")

# === 5. Export summary statistics ===
summary_file = os.path.join(plot_dir, "analysis_summary.txt")
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("Taiwan Satellite Observation Analysis Summary\n")
    f.write("="*80 + "\n\n")
    
    f.write("### Analysis 1: Multi-Point Observation of Satellites ###\n\n")
    f.write(f"Probability that a satellite is observed by multiple points: {multi_observer_prob:.2f}%\n")
    f.write(f"Average observation points per satellite: {satellite_observers['num_observers'].mean():.2f}\n")
    f.write(f"Median observation points per satellite: {satellite_observers['num_observers'].median():.0f}\n")
    f.write(f"Max observation points for a satellite: {satellite_observers['num_observers'].max()}\n\n")
    
    f.write("Distribution of observation points:\n")
    for n_obs, count in observer_count_distribution.items():
        probability = count / len(satellite_observers) * 100
        f.write(f"  {n_obs} point(s): {count} occurrences ({probability:.2f}%)\n")
    
    f.write("\n### Analysis 2: Multi-Satellite Observation from Each Point ###\n\n")
    f.write(f"Probability that an observation point sees multiple satellites: {multi_satellite_prob:.2f}%\n")
    f.write(f"Average satellites per observation point: {observer_satellites['num_satellites'].mean():.2f}\n")
    f.write(f"Median satellites per observation point: {observer_satellites['num_satellites'].median():.0f}\n")
    f.write(f"Max satellites at one point: {observer_satellites['num_satellites'].max()}\n\n")
    
    f.write("Distribution of simultaneous satellites:\n")
    for n_sats, count in satellite_count_distribution.items():
        probability = count / len(observer_satellites) * 100
        f.write(f"  {n_sats} satellite(s): {count} occurrences ({probability:.2f}%)\n")
    
    f.write("\n### Per Location Statistics ###\n\n")
    for location in sorted(max_simultaneous.index):
        f.write(f"{location:15s}: Max={max_simultaneous[location]:2d} satellites, Avg={avg_simultaneous[location]:.2f} satellites\n")

print(f"✅ Saved: {summary_file}")

print("\n" + "="*80)
print("🎉 Analysis complete! Generated 3 plots and 1 summary file.")
print("="*80)
print(f"\n📁 All outputs saved to: {plot_dir}/")
print(f"   1. taiwan_observation_distribution.png - Distribution analysis")
print(f"   2. taiwan_observation_timeline.png - Time series & heatmap")
print(f"   3. taiwan_observation_probability.png - Probability analysis")
print(f"   4. analysis_summary.txt - Text summary")
