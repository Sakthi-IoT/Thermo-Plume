"""
THERMO-PLUME — Layer 3, Agent 2: Calibration Drift Agent
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
Remember the deliberate bug we built into edge_node.py? Every node's
VOC sensor falsely reads HIGHER whenever humidity rises, even if
there's no real extra pollution (this is the "sensor cross-sensitivity"
problem named directly in the problem statement's Hard Part).

This agent's job is to CORRECT that bug, using the exact method the
problem statement names: "cross-calibrates gas sensor nodes against
high-accuracy reference nodes using edge regression."

HOW THE CORRECTION WORKS:
----------------------------
1. We treat the REFERENCE node's readings as "ground truth" (we assume
   it's a more expensive, more accurate sensor).
2. We collect pairs of (humidity, VOC error) from the reference node
   over time — where "VOC error" = how much its OWN reading has been
   pushed off from a calm baseline by humidity.
3. We fit a simple LINEAR REGRESSION: error = slope * humidity + intercept
4. We apply that same correction formula to EVERY node's readings,
   subtracting out the humidity-caused error.

This is a real, working implementation of "edge regression" — small
enough to run on a microcontroller (it's just one multiplication and
one subtraction per reading, once the regression line is learned).

HOW TO USE THIS FILE:
----------------------
    python3 calibration_agent.py

This trains the calibration on simulated reference data, then shows
a BEFORE/AFTER comparison proving the correction actually works.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "nodes"))
from edge_node import EdgeNode


class CalibrationAgent:
    def __init__(self):
        # slope and intercept of our learned correction line
        # error_estimate = slope * humidity + intercept
        self.slope = 0.0
        self.intercept = 0.0
        self.is_calibrated = False

    def train_from_reference(self, reference_node, num_samples=200):
        """
        Watches the reference node for `num_samples` ticks, and learns
        the relationship between humidity and the VOC reading error
        (voc_reported - voc_true) using simple linear regression.

        Because the reference node ALSO has the same bug built in (all
        nodes use the same EdgeNode class), watching its own error is a
        stand-in for what a real calibration process would do: compare
        against a known-good lab reference instrument periodically.
        """
        humidity_values = []
        error_values = []

        for _ in range(num_samples):
            reading = reference_node.read_sensors()
            error = reading["voc_reported"] - reading["voc_true"]
            humidity_values.append(reading["humidity"])
            error_values.append(error)

        # --- Simple linear regression by hand (no extra libraries needed) ---
        # This is small enough to be genuinely "edge-deployable" —
        # just two numbers (slope, intercept) once trained.
        n = len(humidity_values)
        mean_h = sum(humidity_values) / n
        mean_e = sum(error_values) / n

        numerator = sum((humidity_values[i] - mean_h) * (error_values[i] - mean_e) for i in range(n))
        denominator = sum((humidity_values[i] - mean_h) ** 2 for i in range(n))

        self.slope = numerator / denominator if denominator != 0 else 0
        self.intercept = mean_e - self.slope * mean_h
        self.is_calibrated = True

        print(f"Calibration trained: error ≈ {self.slope:.4f} * humidity + {self.intercept:.4f}")

    def correct(self, reading):
        """
        Applies the learned correction to ONE reading's VOC value.
        Returns a NEW value: voc_calibrated (does not modify the
        original reading dict).
        """
        if not self.is_calibrated:
            # If we haven't trained yet, just pass the value through unchanged
            return reading["voc_reported"]

        estimated_error = self.slope * reading["humidity"] + self.intercept
        voc_calibrated = reading["voc_reported"] - estimated_error
        return max(0, voc_calibrated)  # VOC can't be negative


# ---------------------------------------------------------------------------
# DEMO: run this file directly to prove the calibration actually improves accuracy
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Step 1: train the calibration agent using a reference node
    reference_node = EdgeNode(node_id="REF", zone_name="Reference", x=0, y=0, is_reference=True)
    agent = CalibrationAgent()
    agent.train_from_reference(reference_node, num_samples=300)

    # Step 2: test it on a DIFFERENT node it has never seen, to prove it generalizes
    test_node = EdgeNode(node_id="A2", zone_name="Classroom B", x=1, y=0)

    print("\nBEFORE vs AFTER calibration (10 sample readings from a new node):")
    print(f"{'voc_true':>10} | {'voc_reported (buggy)':>22} | {'voc_calibrated (fixed)':>24} | {'error before':>13} | {'error after':>12}")
    print("-" * 95)

    total_error_before = 0
    total_error_after = 0
    for _ in range(10):
        reading = test_node.read_sensors()
        calibrated = agent.correct(reading)

        error_before = abs(reading["voc_reported"] - reading["voc_true"])
        error_after = abs(calibrated - reading["voc_true"])
        total_error_before += error_before
        total_error_after += error_after

        print(f"{reading['voc_true']:>10.2f} | {reading['voc_reported']:>22.2f} | "
              f"{calibrated:>24.2f} | {error_before:>13.2f} | {error_after:>12.2f}")

    print("-" * 95)
    print(f"Average error BEFORE calibration: {total_error_before/10:.2f}")
    print(f"Average error AFTER calibration:  {total_error_after/10:.2f}")
    improvement = (1 - (total_error_after / total_error_before)) * 100
    print(f"Error reduced by {improvement:.1f}%")
