"""
THERMO-PLUME — Layer 1.5, Step 1: Dataset Generator
=====================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
To train a machine learning model, we need lots of EXAMPLE data with
correct "answers" attached (this is called "labeled data"). A model
learns by looking at thousands of examples like:

    "when PM2.5 was 85, PM10 was 120, CO2 was 1600... that was a
     STAGNATION_PREDICTED situation"

This file runs our simulated building (Layer 1) for many, many ticks,
and for each reading, automatically calculates the correct label based
on how bad the pollution actually is. Then it saves everything to a
CSV file — a simple spreadsheet-style file that the model training
script (Step 2) will read.

WHY THE LABELING RULE MATTERS:
--------------------------------
We label based on the TRUE pollutant severity (using voc_true, the
clean value, not the buggy voc_reported). This matters because the
"correct answer" for training must reflect REAL air quality, not a
sensor's flawed reading of it. The model will still be given the buggy
voc_reported as an INPUT feature (because that's what a real sensor
would give it) — but the ANSWER it's trained on is based on the truth.
This is exactly how real-world sensor calibration/ML systems are built.

HOW TO USE THIS FILE:
----------------------
    python3 generate_dataset.py

This creates a file called training_data.csv in the same folder.
"""

import csv
import sys
import os

# allow importing edge_node.py and node_manager.py from the ../nodes folder
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "nodes"))
from  node_manager import NodeManager


def label_reading(reading):
    """
    Looks at ONE sensor reading and decides which of the 3 classes it
    belongs to, based on real thresholds for indoor air quality:

        NORMAL               - everything within safe/typical ranges
        RISING_RISK          - one or more values noticeably elevated
        STAGNATION_PREDICTED - multiple values badly elevated together
                                (this is the "about to become hazardous"
                                 state the problem statement wants us to
                                 predict BEFORE it crosses hazard limits)

    We use voc_true (the clean, bug-free value) for labeling, NOT
    voc_reported, because the label must represent the real situation.
    """
    pm25 = reading["pm25"]
    pm10 = reading["pm10"]
    co2 = reading["co2"]
    voc = reading["voc_true"]

    # Count how many pollutants are significantly elevated
    danger_points = 0
    if pm25 > 35:
        danger_points += 1
    if pm10 > 50:
        danger_points += 1
    if co2 > 1000:
        danger_points += 1
    if voc > 400:
        danger_points += 1

    # Also check for a SEVERE single reading (e.g. CO2 very high alone
    # is still dangerous even if nothing else is elevated yet)
    severe_single = pm25 > 75 or pm10 > 100 or co2 > 1500 or voc > 700

    if danger_points >= 3 or severe_single:
        return "STAGNATION_PREDICTED"
    elif danger_points >= 1:
        return "RISING_RISK"
    else:
        return "NORMAL"


def generate_dataset(num_ticks=3000, output_file="training_data.csv"):
    """
    Runs the simulated building for `num_ticks` ticks, labels every
    reading from every zone, and writes it all to a CSV file.
    """
    manager = NodeManager()

    # These are the columns the model will actually be trained on.
    # Note: voc_reported is included (the buggy sensor value) because
    # that's genuinely what a real device would measure and send.
    fieldnames = [
        "pm25", "pm10", "co2", "humidity", "temperature", "voc_reported",
        "label"
    ]

    rows_written = 0
    label_counts = {"NORMAL": 0, "RISING_RISK": 0, "STAGNATION_PREDICTED": 0}

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for tick in range(num_ticks):
            readings = manager.read_all()
            for r in readings:
                label = label_reading(r)
                writer.writerow({
                    "pm25": r["pm25"],
                    "pm10": r["pm10"],
                    "co2": r["co2"],
                    "humidity": r["humidity"],
                    "temperature": r["temperature"],
                    "voc_reported": r["voc_reported"],
                    "label": label,
                })
                rows_written += 1
                label_counts[label] += 1

    print(f"Done. Wrote {rows_written} labeled rows to '{output_file}'")
    print("\nLabel distribution (how many examples of each class):")
    for label, count in label_counts.items():
        pct = (count / rows_written) * 100
        print(f"  {label:<22} {count:>6}  ({pct:.1f}%)")


if __name__ == "__main__":
    generate_dataset(num_ticks=3000)
