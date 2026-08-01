"""
THERMO-PLUME — Layer 3, Agent 1: Edge Sensing Node Agent
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
This is a thin wrapper around the trained model from Layer 1.5
(model.joblib). Its ONLY job is: given one sensor reading, output
which of the 3 air quality states it belongs to.

Why wrap it in a class instead of just calling the model directly
everywhere? Because the problem statement describes this as a
dedicated "agent" with one clear responsibility ("classify air quality
anomalies"). Keeping it as its own small module means the orchestrator
(Layer 4) can call `sensing_agent.classify(reading)` without knowing
or caring HOW the classification happens internally.

HOW TO USE THIS FILE:
----------------------
    python3 sensing_agent.py

Runs a few example readings through the agent to prove it works.
"""

import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model", "model.joblib")
FEATURE_ORDER = ["pm25", "pm10", "co2", "humidity", "temperature", "voc_reported"]


class SensingAgent:
    def __init__(self, model_path=MODEL_PATH):
        self.model = joblib.load(model_path)

    def classify(self, reading):
        """
        Takes ONE reading (a dict, like what EdgeNode.read_sensors()
        returns) and returns the predicted state as a string:
        "NORMAL", "RISING_RISK", or "STAGNATION_PREDICTED"
        """
        import pandas as pd
        # Build a single-row DataFrame with the EXACT column order/names
        # the model was trained on (avoids a harmless but noisy sklearn
        # warning about missing feature names).
        features = pd.DataFrame([[reading[col] for col in FEATURE_ORDER]], columns=FEATURE_ORDER)
        prediction = self.model.predict(features)
        return prediction[0]


# ---------------------------------------------------------------------------
# DEMO: run this file directly to test the sensing agent on example readings
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent = SensingAgent()

    test_cases = [
        {"pm25": 12, "pm10": 20, "co2": 500, "humidity": 45, "temperature": 24, "voc_reported": 150},
        {"pm25": 40, "pm10": 55, "co2": 950, "humidity": 46, "temperature": 24, "voc_reported": 300},
        {"pm25": 90, "pm10": 130, "co2": 1800, "humidity": 50, "temperature": 25, "voc_reported": 750},
    ]

    for i, reading in enumerate(test_cases, 1):
        result = agent.classify(reading)
        print(f"Test {i}: {reading} -> {result}")
