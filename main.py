import argparse
import util

from pathlib import Path
from card_renderer import load_config, render_card

parser = argparse.ArgumentParser(description="Generate a summary card for every saved jump")
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
# Import once, then generate a card for every jump in the merged dataset.
json_data = util.convert_csv_to_json(filepath, filepath_output)

for jump in json_data:
    jump_num = jump['jumpNumber']
    output_card = output_dir / f'jump_{jump_num}_card.png'
    altitudes = jump.get('data(feet)', [])
    deploy_alt = jump['depAltitude(feet)']
    speed_data = util.jumptrack_speed_metrics(
        altitudes, deploy_alt_ft=deploy_alt, unit='kmh'
    )
    phase_times = util.jump_phase_times(altitudes, deploy_alt)
    render_card(jump, speed_data, phase_times, config, output_card)
    print(f'Social Media Card successfully generated: {output_card}')

print(f'Generated {len(json_data)} jump cards in {output_dir}')