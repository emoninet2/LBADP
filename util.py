import os
import json
import tempfile
import pandas as pd
import numpy as np


METADATA_FIELDS = (
    'dropzone', 'country', 'aircraft', 'canopy', 'canopySize',  # canopySize: square feet
    'jumpType', 'nWay', 'rig', 'exitWeight(kg)', 'weather', 'notes',
    'landingDistanceFromTarget(m)', 'equipmentNotes',
    'verifierName', 'verifierCredentialType', 'verifierCredentialNumber',
    'verifyingSignature',
)


def _ordered_jump(jump):
    """Keep editable metadata above the long altitude sample array."""
    result = {key: value for key, value in jump.items()
              if key not in METADATA_FIELDS and key != 'data(feet)'}
    result.update({key: jump.get(key) for key in METADATA_FIELDS})
    if 'data(feet)' in jump:
        result['data(feet)'] = jump['data(feet)']
    return result


def _confirm_jump_overwrite(existing, incoming, differences):
    print(f"Jump #{incoming['jumpNumber']} differs from the saved data:")
    for key in differences:
        old, new = existing.get(key), incoming[key]
        if key == 'data(feet)':
            old_samples = old if isinstance(old, list) else []
            new_samples = new if isinstance(new, list) else []
            changed = sum(a != b for a, b in zip(old_samples, new_samples))
            changed += abs(len(old_samples) - len(new_samples))
            print(f"  {key}: {len(old_samples)} -> {len(new_samples)} samples; "
                  f"{changed} changed positions")
        else:
            print(f"  {key}: {str(old)[:120]!r} -> {str(new)[:120]!r}")
    while True:
        try:
            answer = input('Skip or overwrite this jump? [s/o, default: skip] ').strip().lower()
        except EOFError:
            print('No response available; skipping this jump.')
            return False
        if answer in ('', 's', 'skip'):
            return False
        if answer in ('o', 'overwrite'):
            return True
        print("Enter 'skip' or 'overwrite'.")


def convert_csv_to_json(csv_filepath, json_filepath=None):
    """Merge by jumpNumber, prompting before replacing conflicting values.

    Existing jumps absent from the CSV and manually entered metadata are kept.
    Unknown metadata is null. Identical imports do not rewrite the output file.
    exitWeight(kg) is the jumper's total weight including equipment.
    """
    previous_records = []
    original_text = None
    if json_filepath and os.path.exists(json_filepath):
        with open(json_filepath, encoding='utf-8') as f:
            original_text = f.read()
        previous_records = json.loads(original_text)
        if not isinstance(previous_records, list):
            raise ValueError('Saved jump JSON must contain a list of jumps')

    records = []
    by_number = {}
    for jump in previous_records:
        number = jump.get('jumpNumber')
        if number is None or number in by_number:
            raise ValueError('Saved jumps must have unique, non-null jumpNumber values')
        by_number[number] = len(records)
        records.append(_ordered_jump(jump))

    df = pd.read_csv(csv_filepath)
    if 'jumpNumber' not in df or df['jumpNumber'].isna().any() or df['jumpNumber'].duplicated().any():
        raise ValueError('CSV jumps must have unique, non-null jumpNumber values')
    if 'data(feet)' in df.columns:
        df['data(feet)'] = df['data(feet)'].apply(
            lambda value: [] if pd.isna(value) else [int(v) for v in str(value).split()]
        )
    incoming_records = df.to_dict(orient='records')
    added = skipped = overwritten = 0
    for incoming in incoming_records:
        incoming = {key: (None if not isinstance(value, list) and pd.isna(value) else value)
                    for key, value in incoming.items()}
        # Blank CSV metadata does not erase user-entered values.
        incoming = {key: value for key, value in incoming.items()
                    if key not in METADATA_FIELDS or
                    (value is not None and not (isinstance(value, str) and not value.strip()))}
        number = incoming['jumpNumber']
        if number not in by_number:
            by_number[number] = len(records)
            records.append(_ordered_jump(incoming))
            added += 1
            continue
        index = by_number[number]
        existing = records[index]
        differences = [key for key, value in incoming.items()
                       if key not in existing or existing[key] != value]
        if not differences:
            skipped += 1
        elif _confirm_jump_overwrite(existing, incoming, differences):
            records[index] = _ordered_jump({**existing, **incoming})
            overwritten += 1
        else:
            skipped += 1

    if json_filepath:
        # Normalize metadata placement once, but preserve the file byte-for-byte
        # on subsequent unchanged imports (including its modification time).
        schema_changed = any(list(old) != list(new)
                             for old, new in zip(previous_records, records))
        if original_text is None or records != previous_records or schema_changed:
            directory = os.path.dirname(os.path.abspath(json_filepath))
            os.makedirs(directory, exist_ok=True)
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                                 dir=directory, delete=False) as f:
                    temp_path = f.name
                    json.dump(records, f, indent=4, allow_nan=False)
                    f.write('\n')
                os.replace(temp_path, json_filepath)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
    print(f'Import: {added} added, {skipped} skipped, {overwritten} overwritten.')
    return records


def get_jump_by_number(json_data, jump_number):
    return next((jump for jump in json_data if jump.get('jumpNumber') == jump_number), None)


def jumptrack_speed_metrics(altitudes, deploy_alt_ft=3000, unit='kmh'):
    altitudes = np.asarray(altitudes)
    sample_rate_hz = 4.0
    dt = 1.0 / sample_rate_hz
    
    # Time steps array (seconds)
    time_sec = np.arange(len(altitudes) - 1) * dt
    
    # Unit conversion multiplier from ft/s
    multiplier = 1.09728 if unit.lower() == 'kmh' else 0.681818
    
    # Raw speed array
    raw_speed = -np.diff(altitudes) / dt * multiplier
    
    # JumpTrack Smoothed Speed Array (6.5s moving average window = 26 samples)
    window_samples = int(6.5 * sample_rate_hz)
    smoothed_speed = np.convolve(raw_speed, np.ones(window_samples) / window_samples, mode='same')
    
    # Find deployment index where altitude drops below deployment altitude
    deploy_indices = np.where(altitudes <= deploy_alt_ft)[0]
    deploy_idx = deploy_indices[0] if len(deploy_indices) > 0 else len(altitudes) - 1

    # --- 1. Freefall Metrics (Exit to Deployment) ---
    ff_smoothed = smoothed_speed[:deploy_idx]
    ff_max_speed = float(np.max(ff_smoothed)) if len(ff_smoothed) > 0 else 0.0
    
    try:
        idx_start = np.where(altitudes <= 12500)[0][0]
        idx_end = np.where(altitudes <= 5000)[0][0]
        
        alt_drop = (altitudes[idx_start] - altitudes[idx_end]) * (0.3048 if unit.lower() == 'kmh' else 1.0)
        duration_sec = (idx_end - idx_start) * dt
        # Speed in km/h or mph
        factor = 3.6 if unit.lower() == 'kmh' else 0.681818 / (1/dt) 
        ff_avg_speed = (alt_drop / duration_sec) * 3.6 if unit.lower() == 'kmh' else (alt_drop / duration_sec) * 0.681818 * (1/0.3048)
    except IndexError:
        ff_avg_speed = float(np.mean(raw_speed[:deploy_idx])) if deploy_idx > 0 else 0.0

    # --- 2. Canopy Metrics (Deployment to Landing) ---
    canopy_smoothed = smoothed_speed[deploy_idx:]
    canopy_raw = raw_speed[deploy_idx:]
    
    canopy_max_speed = float(np.max(canopy_smoothed)) if len(canopy_smoothed) > 0 else 0.0
    canopy_avg_speed = float(np.mean(canopy_raw)) if len(canopy_raw) > 0 else 0.0

    return {
        "unit": unit.lower(),
        "time_sec": np.round(time_sec, 2).tolist(),
        "raw_speed": np.round(raw_speed, 1).tolist(),
        "jumptrack_speed": np.round(smoothed_speed, 1).tolist(),
        "ff_max_speed": round(ff_max_speed, 1),
        "ff_avg_speed": round(ff_avg_speed, 1),
        "canopy_max_speed": round(canopy_max_speed, 1),
        "canopy_avg_speed": round(canopy_avg_speed, 1)
    }

def jump_phase_times(altitudes, deploy_alt_ft, sample_rate_hz=4.0):
    """Estimate phase times from altitude samples.

    Landing is the first ground-level sample after deployment. Missing
    crossings stay unavailable; recording end is not assumed to be landing.
    """
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    deployment = next((i for i in range(1, len(altitudes))
                       if altitudes[i - 1] > deploy_alt_ft >= altitudes[i]), None)
    landing = None
    if deployment is not None:
        landing = next((i for i in range(deployment + 1, len(altitudes))
                        if altitudes[i] <= 0), None)
    return {
        "deployment_sec": deployment / sample_rate_hz if deployment is not None else None,
        "landing_sec": landing / sample_rate_hz if landing is not None else None,
        "canopy_duration_sec": (landing - deployment) / sample_rate_hz
                               if landing is not None else None,
    }
