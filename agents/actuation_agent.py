"""
THERMO-PLUME — Layer 3, Agent 3: Actuation Controller Agent
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
This agent decides how hard the HVAC dampers/fans should run, based on
the Sensing Agent's prediction (NORMAL / RISING_RISK / STAGNATION_PREDICTED).

The naive approach would be: "just set fan speed based on the current
prediction, every single tick." But the problem statement specifically
warns against this — it calls out "thermal-ventilation HUNTING LOOPS"
as a Hard Part to solve. A hunting loop is when a system rapidly
flips between states (fan ON, OFF, ON, OFF...) because it's reacting
to every tiny fluctuation. This wastes energy, wears out hardware, and
looks broken in a live demo.

THIS AGENT PREVENTS HUNTING WITH TWO CLASSIC CONTROL-SYSTEMS TECHNIQUES:

1. HYSTERESIS (persistence check): don't change the actuation state
   unless the new prediction has been seen for several ticks IN A ROW.
   One noisy blip shouldn't flip the fans on.

2. MINIMUM DWELL TIME: once the actuator changes state, it must stay
   in that state for a minimum number of ticks before it's allowed to
   change again — even if the prediction changes back immediately.
   This mimics how real HVAC systems are protected (compressors, for
   example, have mandatory "off" periods to prevent damage).

HOW TO USE THIS FILE:
----------------------
    python3 actuation_agent.py

Runs a simulated noisy sequence of predictions through the agent and
shows how it stays stable instead of flapping on every change.
"""


class ActuationAgent:
    # Maps each predicted state to a target damper/fan percentage
    STATE_TO_PERCENT = {
        "NORMAL": 20,             # low background ventilation
        "RISING_RISK": 55,        # medium — start clearing the air
        "STAGNATION_PREDICTED": 90,  # high — aggressive air exchange
    }

    def __init__(self, persistence_required=3, min_dwell_ticks=5):
        """
        persistence_required: how many ticks IN A ROW the new prediction
                               must appear before we act on it (hysteresis)
        min_dwell_ticks:       minimum ticks the actuator must hold its
                                current state before it's allowed to change
        """
        self.persistence_required = persistence_required
        self.min_dwell_ticks = min_dwell_ticks

        self.current_state = "NORMAL"
        self.current_percent = self.STATE_TO_PERCENT["NORMAL"]

        self._pending_state = None
        self._pending_count = 0
        self._ticks_since_last_change = self.min_dwell_ticks  # allow immediate first change

    def decide(self, predicted_state):
        """
        Call this once per tick with the Sensing Agent's latest
        prediction. Returns the CURRENT actuator percentage (which may
        or may not have changed this tick, depending on hysteresis and
        dwell-time rules).
        """
        self._ticks_since_last_change += 1

        # --- Hysteresis: track how many ticks in a row we've seen this state ---
        if predicted_state == self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = predicted_state
            self._pending_count = 1

        # --- Decide whether to actually apply a change ---
        persistence_met = self._pending_count >= self.persistence_required
        dwell_time_met = self._ticks_since_last_change >= self.min_dwell_ticks
        state_is_different = predicted_state != self.current_state

        if state_is_different and persistence_met and dwell_time_met:
            self.current_state = predicted_state
            self.current_percent = self.STATE_TO_PERCENT[predicted_state]
            self._ticks_since_last_change = 0
            self._pending_count = 0  # reset after acting on it

        return self.current_percent

    def get_state(self):
        """Returns the actuator's current committed state (for logging/dashboard)."""
        return {
            "actuation_state": self.current_state,
            "actuation_pct": self.current_percent,
        }


# ---------------------------------------------------------------------------
# DEMO: run this file directly to see hysteresis prevent a hunting loop
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent = ActuationAgent(persistence_required=3, min_dwell_ticks=5)

    # A deliberately NOISY sequence of predictions — flickers back and forth
    # every tick, like a real noisy sensor near a threshold boundary would.
    noisy_predictions = [
        "NORMAL", "RISING_RISK", "NORMAL", "RISING_RISK", "NORMAL",  # flickering
        "RISING_RISK", "RISING_RISK", "RISING_RISK", "RISING_RISK",  # now persistent
        "NORMAL", "RISING_RISK", "NORMAL",                            # flickering again
        "STAGNATION_PREDICTED", "STAGNATION_PREDICTED", "STAGNATION_PREDICTED",  # persistent
        "NORMAL",
    ]

    print(f"{'tick':>4} | {'raw prediction':>22} | {'actuator %':>10} | changed?")
    print("-" * 55)
    last_pct = None
    change_count = 0
    for i, pred in enumerate(noisy_predictions, 1):
        pct = agent.decide(pred)
        changed = pct != last_pct
        if changed and last_pct is not None:
            change_count += 1
        marker = "  <-- CHANGED" if (changed and last_pct is not None) else ""
        print(f"{i:>4} | {pred:>22} | {pct:>10} |{marker}")
        last_pct = pct

    print("-" * 55)
    print(f"\nRaw predictions flickered {sum(1 for i in range(1, len(noisy_predictions)) if noisy_predictions[i] != noisy_predictions[i-1])} times")
    print(f"Actuator only actually changed {change_count} times")
    print("This gap proves hysteresis + dwell time successfully prevented hunting.")
