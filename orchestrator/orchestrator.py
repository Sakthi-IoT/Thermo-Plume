"""
THERMO-PLUME — Layer 4: Orchestration Loop
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
This is the file that makes THERMO-PLUME an actual SYSTEM instead of a
folder of separate parts. It runs the full "closed loop" the problem
statement asks for:

    SENSE -> CALIBRATE -> PREDICT -> ACTUATE -> AUDIT ENERGY -> STORE
    (and this repeats every tick, forever)

This is "Cyber-Physical Closed-Loop Control" made real: sensor
readings affect a decision, that decision affects the (simulated)
physical world (dampers/fans), and the loop keeps running continuously.

WHAT HAPPENS ON EVERY SINGLE TICK:
--------------------------------------
For EACH of the 5 zones:
  1. SENSE     — read the zone's simulated sensors (Layer 1)
  2. CALIBRATE — fix the humidity/VOC bug (Layer 3, Calibration Agent)
  3. PREDICT   — classify air quality state (Layer 3, Sensing Agent)
  4. ACTUATE   — decide damper/fan % with anti-hunting logic (Layer 3,
                 Actuation Agent) — each zone has its OWN actuation
                 agent, because each zone's HVAC is controlled
                 independently
  5. AUDIT     — log energy usage for this zone (Layer 3, Energy Agent)
  6. SAFETY    — check for a HITL (Human-in-the-Loop) alert condition
  7. BUFFER    — push the full result into that zone's ring buffer
                 (Layer 2)

Then, every SYNC_INTERVAL ticks, ALL zones' ring buffers get flushed
to the SQLite database in one batch (Layer 2) — this matches
"synchronized periodically," not on every single reading.

HOW TO USE THIS FILE:
----------------------
    python3 orchestrator.py

Runs the full closed loop for a set number of ticks and prints a
live-ish log, then a final summary report at the end.
"""

import sys
import os
import time
import random

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "nodes"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "storage"))

from node_manager import NodeManager
from calibration_agent import CalibrationAgent
from sensing_agent import SensingAgent
from actuation_agent import ActuationAgent
from energy_agent import EnergyAuditor
from storage import RingBuffer, Storage

# --- Safety thresholds (Human-in-the-Loop guardrails) ---
VOC_TOXIC_THRESHOLD = 600           # trigger an alert if calibrated VOC exceeds this
ACTUATION_FAILURE_PROBABILITY = 0.01  # 1% chance per tick a simulated actuator "fails"

SYNC_INTERVAL_TICKS = 10  # how often to flush ring buffers to the database
RING_BUFFER_SIZE = 15


class Orchestrator:
    def __init__(self):
        print("Booting THERMO-PLUME orchestrator...\n")

        self.node_manager = NodeManager()

        # --- Train the calibration agent BEFORE the main loop starts ---
        # (mirrors a real system doing a calibration pass at startup)
        print("Training Calibration Agent against reference node...")
        self.calibration_agent = CalibrationAgent()
        # We temporarily "warm up" using the reference node's own stream.
        # This runs the reference node forward some ticks purely for
        # calibration training purposes.
        for node in self.node_manager.nodes:
            if node.node_id == self.node_manager.get_reference_node_id():
                self.calibration_agent.train_from_reference(node, num_samples=300)
                break
        print()

        self.sensing_agent = SensingAgent()

        # Each zone gets its OWN actuation agent (independent HVAC control
        # per room) and its OWN ring buffer (independent local memory,
        # exactly like a real distributed edge deployment would have).
        self.actuation_agents = {
            node.node_id: ActuationAgent(persistence_required=3, min_dwell_ticks=5)
            for node in self.node_manager.nodes
        }
        self.ring_buffers = {
            node.node_id: RingBuffer(max_size=RING_BUFFER_SIZE)
            for node in self.node_manager.nodes
        }
        self.energy_auditors = {
            node.node_id: EnergyAuditor()
            for node in self.node_manager.nodes
        }

        self.storage = Storage(db_path=os.path.join(
            os.path.dirname(__file__), "..", "storage", "thermoplume.db"
        ))

        self.tick_count = 0
        self.safety_alerts = []

    def run_one_tick(self):
        """Runs ONE full sense->calibrate->predict->actuate->audit->store cycle."""
        self.tick_count += 1
        readings = self.node_manager.read_all()

        for reading in readings:
            node_id = reading["node_id"]

            # --- 2. CALIBRATE ---
            voc_calibrated = self.calibration_agent.correct(reading)
            reading["voc_calibrated"] = voc_calibrated

            # --- 3. PREDICT ---
            # Feed the CALIBRATED voc value into the sensing agent, so the
            # prediction benefits from the calibration fix.
            reading_for_model = dict(reading)
            reading_for_model["voc_reported"] = voc_calibrated
            predicted_state = self.sensing_agent.classify(reading_for_model)
            reading["predicted_state"] = predicted_state

            # --- 4. ACTUATE ---
            actuation_pct = self.actuation_agents[node_id].decide(predicted_state)
            reading["actuation_pct"] = actuation_pct

            # --- 5. AUDIT ENERGY ---
            self.energy_auditors[node_id].log_tick(self.tick_count, actuation_pct, predicted_state)

            # --- 6. SAFETY CHECK (HITL guardrails) ---
            self._check_safety(reading)

            # --- 7. BUFFER (local edge RAM) ---
            self.ring_buffers[node_id].add(reading)

        # --- Periodic sync to database (not every tick — batched) ---
        if self.tick_count % SYNC_INTERVAL_TICKS == 0:
            self._sync_all_buffers()

    def _check_safety(self, reading):
        """
        HITL & Safety Guardrails — matches the problem statement:
        "Automatic manual override request dispatched to facility
        engineers if VOC levels exceed toxic thresholds or physical
        damper actuation fails."
        """
        if reading["voc_calibrated"] > VOC_TOXIC_THRESHOLD:
            alert = (f"[TICK {self.tick_count}] TOXIC VOC ALERT in {reading['zone_name']} "
                     f"— voc_calibrated={reading['voc_calibrated']:.1f} "
                     f"(threshold={VOC_TOXIC_THRESHOLD}). Facility engineer override requested.")
            self.safety_alerts.append(alert)
            print(alert)

        if random.random() < ACTUATION_FAILURE_PROBABILITY:
            alert = (f"[TICK {self.tick_count}] ACTUATOR FAILURE simulated in {reading['zone_name']} "
                     f"— damper did not respond. Facility engineer override requested.")
            self.safety_alerts.append(alert)
            print(alert)

    def _sync_all_buffers(self):
        """Flushes every zone's ring buffer into the SQLite database, then clears it."""
        for node in self.node_manager.nodes:
            buffer = self.ring_buffers[node.node_id]
            if len(buffer) > 0:
                self.storage.sync_buffer(
                    node.node_id, node.zone_name, node.x, node.y, buffer.get_all()
                )
                buffer.clear()

    def print_final_report(self):
        print("\n" + "=" * 60)
        print("FINAL SYSTEM REPORT")
        print("=" * 60)
        print(f"Total ticks run: {self.tick_count}")
        print(f"Total safety alerts triggered: {len(self.safety_alerts)}")

        print("\n--- Energy summary per zone ---")
        for node in self.node_manager.nodes:
            report = self.energy_auditors[node.node_id].compare_against_static_baseline(static_baseline_pct=60)
            if report:
                print(f"{node.zone_name:<14} avg actuation={report['our_avg_actuation_pct']:>6}%  "
                      f"energy saved vs static baseline={report['energy_saved_pct']:>6}%")


if __name__ == "__main__":
    orchestrator = Orchestrator()

    NUM_TICKS = 200
    print(f"Running closed-loop control for {NUM_TICKS} ticks...\n")

    for _ in range(NUM_TICKS):
        orchestrator.run_one_tick()

    orchestrator.print_final_report()
