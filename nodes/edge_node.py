"""
THERMO-PLUME — Layer 1: Virtual Edge Node
==========================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
In the real project, this would be an ESP32 microcontroller sitting in a
classroom or hospital ward, with real gas sensors plugged into it, reading
air quality every few seconds.

We don't have that hardware, so this file PRETENDS to be that ESP32.
It generates realistic-looking sensor numbers instead of real ones.

"Realistic" means:
  1. Numbers don't jump around randomly every second (real sensors drift
     slowly, like a car's speed changing smoothly, not teleporting).
  2. Sometimes a "pollution event" happens (e.g. a classroom gets crowded)
     and readings spike, then slowly come back down.
  3. We deliberately add a BUG on purpose: when humidity goes up, the VOC
     sensor falsely reads higher too, even if there's no real pollution.
     This is a REAL problem mentioned in the problem statement ("VOC
     sensors falsely reacting to humidity spikes"). We add this bug here
     so that later (Layer 3, the Calibration Agent) can fix it — and we
     can PROVE it was fixed, because we know the "true" clean values too.

HOW TO USE THIS FILE:
----------------------
Run it directly to see example output:
    python3 edge_node.py

Or import it elsewhere:
    from edge_node import EdgeNode
    node = EdgeNode(node_id="A1", zone_name="Classroom A", x=0, y=0)
    reading = node.read_sensors()
"""

import random
import math


class EdgeNode:
    """
    Represents ONE virtual sensor node (one "room" or "zone").

    Think of this as a blueprint. Every time you write:
        node = EdgeNode("A1", "Classroom A", x=0, y=0)
    you create one new virtual sensor device.
    """

    def __init__(self, node_id, zone_name, x, y, is_reference=False):
        # --- Identity of this node ---
        self.node_id = node_id          # e.g. "A1"
        self.zone_name = zone_name      # e.g. "Classroom A"
        self.x = x                      # position on the dashboard map
        self.y = y
        self.is_reference = is_reference  # True = "trusted, high-accuracy" node

        # --- Baseline (normal, healthy) air quality levels ---
        # These are realistic-ish starting points for an indoor room.
        self.PM25_BASELINE = 12.0
        self.PM10_BASELINE = 20.0
        self.VOC_BASELINE = 150.0
        self.CO2_BASELINE = 500.0
        self.HUMIDITY_BASELINE = 45.0
        self.TEMPERATURE_BASELINE = 24.0

        self.pm25 = self.PM25_BASELINE
        self.pm10 = self.PM10_BASELINE
        self.voc = self.VOC_BASELINE
        self.co2 = self.CO2_BASELINE
        self.humidity = self.HUMIDITY_BASELINE
        self.temperature = self.TEMPERATURE_BASELINE

 

        # --- Internal "pollution event" state ---
        # This simulates something like "the room just got crowded" or
        # "someone opened a window and pollution drifted in."
        self.event_active = False
        self.event_ticks_left = 0

        # How many readings we've generated (used for smooth waveforms)
        self.tick_count = 0

    def _mean_reverting_step(self, current_value, baseline, volatility, pull_strength=0.05):
        """
        This makes a number drift SLOWLY and REALISTICALLY, instead of
        jumping randomly. It's called "mean-reverting" — the value wanders
        around, but is always gently pulled back toward its normal baseline,
        just like a real sensor in a stable room.

        current_value:  the value right now
        baseline:       the "normal" value it should hover around
        volatility:      how jumpy/noisy it is (small = calm sensor)
        pull_strength:   how strongly it's pulled back to baseline
        """
        pull = (baseline - current_value) * pull_strength
        noise = random.gauss(0, volatility)
        return current_value + pull + noise

    def _maybe_trigger_pollution_event(self):
        """
        Randomly decide if a pollution spike should start.
        (e.g. classroom fills up with students, hospital ward gets busy)
        """
        if not self.event_active:
            # Roughly a 3% chance per tick of a new event starting
            if random.random() < 0.03:
                self.event_active = True
                # Event lasts somewhere between 15 and 40 ticks before fading
                self.event_ticks_left = random.randint(15, 40)

    def read_sensors(self):
        """
        THE MAIN FUNCTION. Call this once per "tick" (once per time step).
        It returns a dictionary of sensor readings, just like an ESP32
        would send over MQTT in the real system.
        """
        self.tick_count += 1
        self._maybe_trigger_pollution_event()

        # --- Step 1: figure out today's baseline (does an event push it up?) ---
        pm25_target = self.PM25_BASELINE
        pm10_target = self.PM10_BASELINE
        voc_target = self.VOC_BASELINE
        co2_target = self.CO2_BASELINE

        if self.event_active:
            # During an event, baselines temporarily rise (pollution buildup)
            pm25_target += 40
            pm10_target += 55
            voc_target += 250
            co2_target += 600
            self.event_ticks_left -= 1
            if self.event_ticks_left <= 0:
                self.event_active = False  # event fades out

        # --- Step 2: drift each value smoothly toward its target ---
        self.pm25 = max(0, self._mean_reverting_step(self.pm25, pm25_target, volatility=1.5))
        self.pm10 = max(0, self._mean_reverting_step(self.pm10, pm10_target, volatility=2.0))
        self.co2 = max(400, self._mean_reverting_step(self.co2, co2_target, volatility=8.0))

        # Humidity/temperature drift slowly around normal room conditions,
        # with a gentle wave pattern (like day/night or HVAC cycling)
        humidity_wave = 5 * math.sin(self.tick_count / 30)
        self.humidity = self._mean_reverting_step(
        self.humidity, self.HUMIDITY_BASELINE + humidity_wave, volatility=1.0
        )
        self.temperature = self._mean_reverting_step(
        self.temperature, self.TEMPERATURE_BASELINE, volatility=0.3
        )
        # --- Step 3: the deliberate VOC "true value" (before the bug) ---
        true_voc = max(0, self._mean_reverting_step(self.voc, voc_target, volatility=6.0))
        self.voc = true_voc  # store the clean value internally

        # --- Step 4: inject the KNOWN sensor bug (humidity cross-sensitivity) ---
        # This is the exact problem named in the brief: "VOC sensors falsely
        # reacting to humidity spikes." We make the REPORTED voc reading
        humidity_error = max(0, self.humidity - self.HUMIDITY_BASELINE) * 3.5
        voc_reported = true_voc + humidity_error

        # --- Step 5: package everything up like a real sensor payload ---
        reading = {
            "node_id": self.node_id,
            "zone_name": self.zone_name,
            "x": self.x,
            "y": self.y,
            "tick": self.tick_count,
            "pm25": round(self.pm25, 2),
            "pm10": round(self.pm10, 2),
            "co2": round(self.co2, 2),
            "humidity": round(self.humidity, 2),
            "temperature": round(self.temperature, 2),
            "voc_reported": round(voc_reported, 2),   # <-- what the "sensor" outputs (buggy)
            "voc_true": round(true_voc, 2),            # <-- kept ONLY so we can grade our fix later
            "event_active": self.event_active,
        }
        return reading


# ---------------------------------------------------------------------------
# DEMO: run this file directly to see 10 ticks of one node's readings
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    node = EdgeNode(node_id="A1", zone_name="Classroom A", x=0, y=0)

    print(f"{'tick':>4} | {'pm25':>6} | {'pm10':>6} | {'co2':>6} | {'humid':>6} | {'voc_rep':>8} | {'voc_true':>8} | event")
    print("-" * 75)
    for _ in range(10):
        r = node.read_sensors()
        print(f"{r['tick']:>4} | {r['pm25']:>6} | {r['pm10']:>6} | {r['co2']:>6} | "
              f"{r['humidity']:>6} | {r['voc_reported']:>8} | {r['voc_true']:>8} | {r['event_active']}")
