"""
THERMO-PLUME — Layer 1 (continued): Node Manager
==================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
edge_node.py gives us ONE virtual sensor (one room).
This file creates and manages SEVERAL of them together, like a real
building with multiple rooms, each with its own sensor node.

Think of it like this:
  - edge_node.py       = the blueprint for one sensor device
  - node_manager.py     = the building manager that has a list of every
                          device installed, and asks all of them for
                          readings at the same time, once per "tick"

One node is marked as the "reference" node — meaning it's treated as the
high-accuracy, trusted sensor that other nodes get calibrated against
later (this matches the "Calibration Drift Agent" requirement in the
problem statement: "cross-calibrates gas sensor nodes against high-
accuracy reference nodes").

HOW TO USE THIS FILE:
----------------------
Run it directly to see one full "tick" across all zones:
    python3 node_manager.py

Or import it elsewhere:
    from node_manager import NodeManager
    manager = NodeManager()
    all_readings = manager.read_all()   # list of dicts, one per zone
"""

from edge_node import EdgeNode


class NodeManager:
    """
    Holds a list of EdgeNode objects (one per zone/room) and lets you
    read all of them together with one function call.
    """

    def __init__(self):
        # --- Define the building layout here ---
        # x, y are just simple coordinates so the dashboard can later
        # draw these zones on a 2D map / heatmap.
        # The FIRST node is marked as the reference (trusted) node.
        self.nodes = [
            EdgeNode(node_id="A1", zone_name="Classroom A", x=0, y=0, is_reference=True),
            EdgeNode(node_id="A2", zone_name="Classroom B", x=1, y=0),
            EdgeNode(node_id="A3", zone_name="Corridor", x=0, y=1),
            EdgeNode(node_id="A4", zone_name="Ward 1", x=1, y=1),
            EdgeNode(node_id="A5", zone_name="Ward 2", x=2, y=1),
        ]

    def read_all(self):
        """
        Ask every node for one new reading (one tick), and return them
        all as a list. This is what the orchestration loop (Layer 4)
        will call once per time step.
        """
        return [node.read_sensors() for node in self.nodes]

    def get_reference_node_id(self):
        """
        Returns the node_id of whichever node is marked as the trusted
        reference sensor. The Calibration Agent (Layer 3) will need this
        to know which node's readings to trust as "ground truth."
        """
        for node in self.nodes:
            if node.is_reference:
                return node.node_id
        return None  # safety fallback if nobody was marked as reference


# ---------------------------------------------------------------------------
# DEMO: run this file directly to see one tick across ALL zones at once
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    manager = NodeManager()

    print("Reference node is:", manager.get_reference_node_id())
    print()

    # Simulate 5 ticks across the whole building
    for tick_num in range(1, 6):
        print(f"--- Tick {tick_num} ---")
        readings = manager.read_all()
        for r in readings:
            ref_tag = " (REFERENCE)" if r["node_id"] == manager.get_reference_node_id() else ""
            print(f"  {r['zone_name']:<12} | pm25={r['pm25']:>6} | co2={r['co2']:>7} | "
                  f"voc_reported={r['voc_reported']:>7} | event={r['event_active']}{ref_tag}")
        print()
