import argparse
import util

from pathlib import Path
from card_renderer import load_config, render_card

parser = argparse.ArgumentParser(description="Generate the jump summary card")
parser.add_argument('--config', default=str(Path(__file__).with_name('card_config.json')))
parser.add_argument('--background', help='Override the background in card_config.json')
args = parser.parse_args()
config = load_config(args.config)
if args.background:
    config['background'] = args.background

# 1. Paths & Setup
filepath = "/home/emon/projects/LBADP/imports/jumps_8e817b90-bbf8-11f1-a696-310d907fd634.csv"
filepath_output = "/home/emon/projects/LBADP/data/data.json"
output_dir = Path(__file__).resolve().parent / 'outputs'
output_dir.mkdir(parents=True, exist_ok=True)
output_card = output_dir / 'jump_35_card.png'

# Load jump data
json_data = util.convert_csv_to_json(filepath, filepath_output)
jump = util.get_jump_by_number(json_data, 35)

if not jump:
    raise ValueError("Jump number 35 not found in dataset.")

# Extract Stats
jump_num = jump.get('jumpNumber', 35)
exit_alt = jump.get('exitAltitude(feet)', 0)
deploy_alt = jump['depAltitude(feet)']
ff_time = jump.get('freeFallTime(sec)', 0)

# The logbook exports true airspeed (TAS) in mph; display it in km/h.
MPH_TO_KMH = 1.609344
max_speed_kmh = jump['maxFreeFallTas(mph)'] * MPH_TO_KMH
ff_avg_speed = jump['avgFreeFallTas(mph)'] * MPH_TO_KMH
canopy_avg_speed = jump['avgCanopyTas(mph)'] * MPH_TO_KMH
canopy_max_speed = jump['maxCanopyTas(mph)'] * MPH_TO_KMH

altitudes = jump.get('data(feet)', [])
speed_data = util.jumptrack_speed_metrics(altitudes, deploy_alt_ft=deploy_alt, unit='kmh')
time_sec = speed_data['time_sec']
speed_kmh = speed_data['jumptrack_speed']
altitudes_plot = altitudes[:len(time_sec)]
phase_times = util.jump_phase_times(altitudes, deploy_alt)
deploy_time = phase_times['deployment_sec']
canopy_duration = phase_times['canopy_duration_sec']
if canopy_duration is None:
    canopy_duration_label = 'N/A'
else:
    duration_seconds = round(canopy_duration)
    canopy_duration_label = f'~{duration_seconds // 60}m {duration_seconds % 60:02d}s'


render_card(jump, speed_data, phase_times, config, output_card)
print(f"Social Media Card successfully generated: {output_card}")
