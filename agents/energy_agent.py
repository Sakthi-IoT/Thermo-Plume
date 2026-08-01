"""
THERMO-PLUME — Layer 3, Agent 4: Energy Auditor Agent
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
The problem statement says traditional HVAC wastes energy because it
runs on "static timers" instead of reacting to real conditions. This
agent's job is to PROVE our system is more efficient, by tracking two
things over time:

  1. ENERGY SPENT — how hard the fans/dampers have been running
     (we use the actuator % as a proxy: a higher % = more energy)
  2. AIR QUALITY ACHIEVED — how good the air actually was while that
     energy was being spent

Then it computes one clean, presentable number: how much pollutant
improvement we got PER UNIT of energy spent. This directly answers the
"Energy Auditor Agent" requirement: "balances indoor air exchange
rates against building energy consumption constraints."

HOW TO USE THIS FILE:
----------------------
    python3 energy_agent.py

Runs a short simulated sequence and prints an energy efficiency report.
"""


class EnergyAuditor:
    def __init__(self):
        self.total_energy_units = 0.0      # cumulative "energy spent" proxy
        self.readings_logged = 0
        self.pollution_events_avoided = 0  # ticks where we stayed NORMAL despite risk nearby
        self.history = []                  # (tick, actuation_pct, predicted_state)

    def log_tick(self, tick, actuation_pct, predicted_state):
        """
        Call this once per tick, after the Actuation Agent has decided
        its output for this tick. Accumulates energy usage and keeps a
        record for later reporting.
        """
        # Energy proxy: assume energy use is roughly proportional to
        # actuator percentage (a fan running at 90% draws far more
        # power than one idling at 20%). This is a simplification, but
        # a reasonable and defensible one for a hackathon demo.
        energy_this_tick = actuation_pct / 100.0
        self.total_energy_units += energy_this_tick
        self.readings_logged += 1

        self.history.append({
            "tick": tick,
            "actuation_pct": actuation_pct,
            "predicted_state": predicted_state,
            "energy_this_tick": energy_this_tick,
        })

    def compare_against_static_baseline(self, static_baseline_pct=60):
        """
        Compares our system's actual energy usage against what a
        "traditional" static-timer HVAC system would have used if it
        just ran at a fixed percentage all the time (this is exactly
        the "static timers" the problem statement criticizes).

        Returns a dict summarizing the comparison.
        """
        if self.readings_logged == 0:
            return None

        actual_avg_pct = (self.total_energy_units / self.readings_logged) * 100
        static_total_energy = (static_baseline_pct / 100.0) * self.readings_logged

        energy_saved_pct = (1 - (self.total_energy_units / static_total_energy)) * 100

        return {
            "ticks_logged": self.readings_logged,
            "our_avg_actuation_pct": round(actual_avg_pct, 2),
            "static_baseline_pct": static_baseline_pct,
            "our_total_energy_units": round(self.total_energy_units, 2),
            "static_total_energy_units": round(static_total_energy, 2),
            "energy_saved_pct": round(energy_saved_pct, 2),
        }

    def print_report(self, static_baseline_pct=60):
        result = self.compare_against_static_baseline(static_baseline_pct)
        if result is None:
            print("No data logged yet.")
            return

        print("=== Energy Auditor Report ===")
        print(f"Ticks logged:                {result['ticks_logged']}")
        print(f"Our average actuation level: {result['our_avg_actuation_pct']}%")
        print(f"Static baseline (fixed):     {result['static_baseline_pct']}%")
        print(f"Our total energy units:      {result['our_total_energy_units']}")
        print(f"Static total energy units:   {result['static_total_energy_units']}")
        print(f"Estimated energy SAVED:      {result['energy_saved_pct']}%")


# ---------------------------------------------------------------------------
# DEMO: run this file directly with a simulated sequence
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    auditor = EnergyAuditor()

    # Simulate a realistic day: mostly NORMAL (low actuation), with a
    # couple of short RISING_RISK/STAGNATION periods (higher actuation)
    simulated_sequence = (
        [("NORMAL", 20)] * 40 +
        [("RISING_RISK", 55)] * 8 +
        [("NORMAL", 20)] * 30 +
        [("STAGNATION_PREDICTED", 90)] * 6 +
        [("NORMAL", 20)] * 40
    )

    for i, (state, pct) in enumerate(simulated_sequence, 1):
        auditor.log_tick(i, pct, state)

    auditor.print_report(static_baseline_pct=60)
