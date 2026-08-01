<div align="center">

# 🌬️ THERMO-PLUME

### Edge-AI Thermal Sensing & Dynamic Clean-Air HVAC Orchestration

*Predicting indoor air pollution before it happens — and acting on it automatically.*

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-Streamlit-FF4B4B?style=for-the-badge)](https://thermo-plume-fq4jflamtmn63a8nozg9cp.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Working_Prototype-brightgreen?style=for-the-badge)

**Problem Statement:** `SDGIOTP001` &nbsp;•&nbsp; **SDG 3** Good Health & Well-being &nbsp;•&nbsp; **SDG 11** Sustainable Cities

</div>

<br>

> *"Air pollution is a quiet killer that spares no one, but its burden falls heaviest on the vulnerable."*
> — Tedros Adhanom Ghebreyesus, WHO Director-General

<br>

## 📌 The Problem

Traditional HVAC systems run on **static timers** and **single-threshold thermostats** — wasting energy and missing dangerous, localized pollutant buildup in crowded schools and hospitals until it's already a health hazard.

**THERMO-PLUME** flips this: distributed edge sensors run TinyML models to **predict** air stagnation *before* it crosses hazard thresholds, then automatically drive HVAC dampers and scrubbers — no cloud round-trip, no static schedule.

<br>

## 🏆 Results at a Glance

<div align="center">

| Metric | Result |
|:---|:---:|
| 🎯 TinyML model size | **1.72 KB** (21 decision nodes) |
| 🔧 Calibration accuracy gain | **73.6%** VOC sensor error reduction |
| 🌀 Hunting-loop prevention | **10 raw flickers → 2 real actuations** |
| ⚡ Energy saved vs. static HVAC | **57%** |
| 📡 Comms | Real MQTT pub/sub, live public broker |

</div>

<br>

## 🧠 How It Works

```
┌─────────────────────────────────────────────────────┐
│  🖥️  LAYER 5 — Live Dashboard (Streamlit)            │
│      heatmap · telemetry · energy chart · alerts     │
├─────────────────────────────────────────────────────┤
│  🔁  LAYER 4 — Orchestrator (Closed-Loop Control)     │
│      sense → calibrate → predict → actuate → audit   │
├─────────────────────────────────────────────────────┤
│  🤖  LAYER 3 — Specialist Agents                      │
│      Sensing · Calibration · Actuation · Energy       │
├─────────────────────────────────────────────────────┤
│  📡  LAYER 2 — Comms & Storage                        │
│      MQTT · Ring Buffers · SQLite                     │
├─────────────────────────────────────────────────────┤
│  📟  LAYER 1 — Virtual Edge Nodes                      │
│      5 simulated zones, realistic sensor drift        │
└─────────────────────────────────────────────────────┘
```

<br>

### 🤖 The Agents

<table>
<tr><td width="30%"><b>🔍 Edge Sensing Node</b></td><td>Classifies air quality as <code>NORMAL</code> / <code>RISING_RISK</code> / <code>STAGNATION_PREDICTED</code> using a Decision Tree small enough to run on an ESP32.</td></tr>
<tr><td><b>🎛️ Calibration Drift</b></td><td>Fixes VOC sensors falsely reacting to humidity spikes, via edge linear regression against a reference node.</td></tr>
<tr><td><b>💨 Actuation Controller</b></td><td>Drives dampers/fans with hysteresis + minimum dwell time — prevents rapid on/off "hunting loops."</td></tr>
<tr><td><b>⚡ Energy Auditor</b></td><td>Tracks duty cycle against a static-timer baseline to quantify real energy savings.</td></tr>
</table>

<br>

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/-scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![Streamlit](https://img.shields.io/badge/-Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![MQTT](https://img.shields.io/badge/-MQTT-660066?style=flat-square&logo=mqtt&logoColor=white)
![Plotly](https://img.shields.io/badge/-Plotly-3F4F75?style=flat-square&logo=plotly&logoColor=white)

<br>

## ⚙️ A Note on Hardware

<details>
<summary><b>Click to expand — why this is a software-first build</b></summary>
<br>

This project was built entirely in software due to hackathon time and hardware constraints. Every component is designed to map directly onto real ESP32/ARM Cortex-M hardware:

- The trained model is already exported to plain C (`model/thermoplume_model.c`) — **1.72 KB, zero dependencies**, ready to paste into real firmware.
- Simulated edge nodes generate realistic, noisy, drifting sensor data — including a deliberately injected humidity/VOC cross-sensitivity bug — so the Calibration Agent solves a real, measurable problem rather than a trivial one.
- Every "Hard Part" named in the problem statement (sensor drift, cross-sensitivity, hunting loops) has a working, proven fix in code — not just a slide claim.

</details>

<br>

## 📁 Project Structure

```
thermoplume/
├── 📟 nodes/              Virtual sensors — realistic drift + injected bug
├── 🧠 model/               Dataset generation, training, C export
├── 📡 storage/             Ring buffers, SQLite, MQTT pub/sub
├── 🤖 agents/              Sensing, Calibration, Actuation, Energy
├── 🔁 orchestrator/        The closed control loop
├── 🖥️ dashboard/           Live Streamlit app
└── requirements.txt
```

<br>

## 🚀 Running It Locally

```bash
# Install dependencies
pip install streamlit plotly pandas scikit-learn joblib

# Generate data + train the model (first time only)
cd model
python generate_dataset.py
python train_model.py
python export_to_c.py
cd ..

# Launch the dashboard
cd dashboard
streamlit run app.py
```

<details>
<summary>Run individual layers standalone</summary>
<br>

```bash
python nodes/node_manager.py          # simulated sensors
python agents/calibration_agent.py    # before/after calibration proof
python agents/actuation_agent.py      # anti-hunting-loop proof
python orchestrator/orchestrator.py   # full closed loop, 200 ticks
```
</details>

<br>

## 💡 Key Engineering Decisions

- **Decision Tree over a neural network** — deliberately chosen for true TinyML deployability: 21 nodes, sub-2KB, compiles to dependency-free C.
- **100% test accuracy, explained honestly** — simulated labels are rule-based, so the classifier correctly rediscovers the generating rules. A transparent starting point for retraining on real sensor data.
- **Hysteresis + minimum dwell time** directly solves the "thermal-ventilation hunting loops" problem named in the brief.
- **Real MQTT**, tested against a live public broker — not a mocked pub/sub.

<br>

---

<div align="center">

Built for the **JCT College of Engineering and Technology** SDG + IoT Hackathon
Problem Statement `SDGIOTP001`

</div>
