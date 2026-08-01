"""
THERMO-PLUME — Layer 5: Live Agent Observability Dashboard
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
This is the visual front-end of the whole project — the thing you'll
actually show judges live. It uses Streamlit, a Python library that
turns a plain script into a web app with almost no extra code.

It directly reuses the Orchestrator from Layer 4 — every button click
here actually runs real ticks of the real closed-loop system (sensing,
calibration, prediction, actuation, energy auditing, safety checks).
This is NOT a separate "fake" dashboard with hardcoded numbers — it's
a live window into the same system you already tested in the terminal.

WHAT'S ON SCREEN:
--------------------
  - A button to advance the simulation forward
  - A red alert banner if any safety event happened recently
  - A "pollutant heatmap" — a colored map of your 5 zones (matches
    "Live Agent Observability Dashboard: real-time... indoor
    pollutant heatmap" from the problem statement)
  - A live table of every zone's current sensor + actuation state
  - A chart of average actuation % over time
  - Energy savings metrics per zone (vs a static-timer baseline)

HOW TO RUN THIS FILE (IMPORTANT — different from other files):
-------------------------------------------------------------------
You do NOT run this with `python app.py`. Streamlit apps are run with:

    pip install streamlit plotly pandas
    streamlit run app.py

This will open a browser tab automatically at http://localhost:8501
"""

import sys
import os
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "orchestrator"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "nodes"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "storage"))

from orchestrator import Orchestrator

st.set_page_config(page_title="THERMO-PLUME", layout="wide")


# --- Keep ONE Orchestrator instance alive across button clicks ---
# Streamlit re-runs the whole script top-to-bottom on every interaction,
# so we use session_state to make sure we don't rebuild (and reset) the
# whole simulation every time someone clicks a button.
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()
    st.session_state.actuation_history = []  # (tick, avg_actuation_pct) for the trend chart

orchestrator = st.session_state.orchestrator


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.title("🌬️ THERMO-PLUME")
st.caption("Edge-AI Thermal Sensing & Dynamic Clean-Air HVAC Orchestration — Live Dashboard")

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    ticks_to_run = st.number_input("Ticks to advance", min_value=1, max_value=100, value=10)
with col2:
    st.write("")  # spacing
    st.write("")
    advance_clicked = st.button("▶ Advance Simulation", type="primary")

if advance_clicked:
    for _ in range(int(ticks_to_run)):
        orchestrator.run_one_tick()
        # record average actuation across all zones for this tick, for the trend chart
        latest_pcts = [agent.current_percent for agent in orchestrator.actuation_agents.values()]
        avg_pct = sum(latest_pcts) / len(latest_pcts)
        st.session_state.actuation_history.append(
            {"tick": orchestrator.tick_count, "avg_actuation_pct": avg_pct}
        )

st.markdown(f"**Total ticks run:** {orchestrator.tick_count}  |  "
            f"**Total safety alerts:** {len(orchestrator.safety_alerts)}")


# ---------------------------------------------------------------------------
# SAFETY ALERT BANNER (Human-in-the-Loop guardrail)
# ---------------------------------------------------------------------------
if orchestrator.safety_alerts:
    recent_alerts = orchestrator.safety_alerts[-3:]  # show the most recent few
    st.error("⚠️ SAFETY ALERT(S) — Facility engineer override requested:\n\n" +
              "\n\n".join(recent_alerts))


# ---------------------------------------------------------------------------
# BUILD CURRENT SNAPSHOT (latest state of every zone)
# ---------------------------------------------------------------------------
rows = []
for node in orchestrator.node_manager.nodes:
    buffer_contents = orchestrator.ring_buffers[node.node_id].get_all()
    if buffer_contents:
        latest = buffer_contents[-1]
    else:
        latest = None

    actuation_state = orchestrator.actuation_agents[node.node_id].get_state()

    rows.append({
        "zone_name": node.zone_name,
        "x": node.x,
        "y": node.y,
        "pm25": latest["pm25"] if latest else None,
        "pm10": latest["pm10"] if latest else None,
        "co2": latest["co2"] if latest else None,
        "voc_calibrated": round(latest["voc_calibrated"], 1) if latest else None,
        "predicted_state": latest["predicted_state"] if latest else "NO DATA YET",
        "actuation_pct": actuation_state["actuation_pct"],
    })

snapshot_df = pd.DataFrame(rows)

STATE_COLOR = {
    "NORMAL": "#2ecc71",              # green
    "RISING_RISK": "#f39c12",         # orange
    "STAGNATION_PREDICTED": "#e74c3c",  # red
    "NO DATA YET": "#95a5a6",         # grey
}


# ---------------------------------------------------------------------------
# LAYOUT: heatmap on the left, table on the right
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1, 1])

with left_col:
    st.subheader("Indoor Pollutant Heatmap")
    fig = go.Figure()
    for _, row in snapshot_df.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["x"]], y=[row["y"]],
            mode="markers+text",
            marker=dict(
                size=60,
                color=STATE_COLOR.get(row["predicted_state"], "#95a5a6"),
                line=dict(width=2, color="white"),
            ),
            text=[row["zone_name"]],
            textposition="bottom center",
            hovertext=f"{row['zone_name']}<br>State: {row['predicted_state']}"
                      f"<br>PM2.5: {row['pm25']}<br>Actuation: {row['actuation_pct']}%",
            hoverinfo="text",
            showlegend=False,
        ))
    fig.update_layout(
        xaxis=dict(visible=False, range=[-0.5, 2.5]),
        yaxis=dict(visible=False, range=[-0.5, 1.5]),
        height=350,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🟢 Normal   🟠 Rising Risk   🔴 Stagnation Predicted")

with right_col:
    st.subheader("Live Node Telemetry")
    st.dataframe(snapshot_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# ENERGY SECTION
# ---------------------------------------------------------------------------
st.subheader("Energy vs. Air-Purity Trade-off")

energy_col1, energy_col2 = st.columns([2, 1])

with energy_col1:
    if st.session_state.actuation_history:
        history_df = pd.DataFrame(st.session_state.actuation_history)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=history_df["tick"], y=history_df["avg_actuation_pct"],
            mode="lines", line=dict(color="#3498db", width=2),
        ))
        fig2.update_layout(
            xaxis_title="Tick", yaxis_title="Avg actuation % (all zones)",
            height=300, margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Click 'Advance Simulation' to start generating data.")

with energy_col2:
    st.markdown("**Energy saved vs. static baseline**")
    for node in orchestrator.node_manager.nodes:
        report = orchestrator.energy_auditors[node.node_id].compare_against_static_baseline(60)
        if report:
            st.metric(node.zone_name, f"{report['energy_saved_pct']}%", help="vs. a fixed 60% static HVAC baseline")
