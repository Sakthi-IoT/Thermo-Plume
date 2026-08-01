"""
THERMO-PLUME — Layer 2, Part B: MQTT Communication Layer
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
MQTT is a lightweight messaging protocol built specifically for IoT
devices — it's the real-world standard for exactly this kind of
project (sensor nodes "publishing" readings, a central system
"subscribing" to listen for them).

Think of MQTT like a radio station:
  - A node "publishes" (broadcasts) its reading on a specific
    "topic" (like a radio channel), e.g. "thermoplume/A1/telemetry"
  - Our orchestrator "subscribes" (tunes in) to that channel and
    receives the message the moment it's sent
  - Multiple nodes can publish on different channels, and one
    listener can subscribe to ALL of them using a wildcard

This file does NOT run its own MQTT server. Instead it connects to a
FREE PUBLIC test broker (test.mosquitto.org) — this is a real,
internet-standard MQTT server anyone can use for testing, no signup,
no cost, no setup. This is the fastest way for a hackathon team to get
real MQTT working without hosting your own broker.

IMPORTANT — READ BEFORE RUNNING:
-----------------------------------
This needs an internet connection AND the paho-mqtt library.
Install it first:
    pip install paho-mqtt

Because test.mosquitto.org is a PUBLIC broker anyone in the world can
use, we pick a fairly unique topic prefix to avoid clashing with other
people's test messages. Feel free to change TOPIC_PREFIX to something
even more unique (e.g. include your team name) if you see unexpected
messages appear.

HOW TO USE THIS FILE:
----------------------
Run the demo directly to see a publish + subscribe test:
    python3 mqtt_client.py

Or import the two functions elsewhere:
    from mqtt_client import publish_reading, start_subscriber
"""

import json
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt is not installed.")
    print("Run this first:  pip install paho-mqtt")
    raise SystemExit(1)


# --- Configuration ---
BROKER_ADDRESS = "test.mosquitto.org"   # free public MQTT broker, no signup needed
BROKER_PORT = 1883
TOPIC_PREFIX = "thermoplume-hackathon-jct"  # change this if you see unexpected messages


def publish_reading(node_id, reading_dict):
    """
    Sends ONE sensor reading out over MQTT, on a topic specific to
    that node, e.g. "thermoplume-hackathon-jct/A1/telemetry"

    In the real system, this is what would run ON the ESP32 itself
    after it takes a sensor reading.
    """
    client = mqtt.Client()
    client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=10)

    topic = f"{TOPIC_PREFIX}/{node_id}/telemetry"
    payload = json.dumps(reading_dict)  # convert the dict to a JSON string to send

    client.publish(topic, payload)
    client.disconnect()
    print(f"Published to '{topic}': {payload}")


def start_subscriber(on_message_callback, timeout_seconds=None):
    """
    Starts listening for messages on ALL node topics at once, using the
    MQTT wildcard "+" (matches any single topic level).
    e.g. "thermoplume-hackathon-jct/+/telemetry" matches every node's
    telemetry topic.

    on_message_callback: a function you provide that takes one argument
    (the decoded reading dictionary) and does something with it —
    e.g. save it to the database, or print it.

    This is what the orchestrator (Layer 4) will run continuously to
    receive readings from every simulated node.
    """
    def _on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to broker. Subscribing to '{TOPIC_PREFIX}/+/telemetry'")
            client.subscribe(f"{TOPIC_PREFIX}/+/telemetry")
        else:
            print(f"Failed to connect, return code {rc}")

    def _on_message(client, userdata, msg):
        try:
            reading = json.loads(msg.payload.decode())
            on_message_callback(reading)
        except json.JSONDecodeError:
            print(f"Received a message that wasn't valid JSON on topic {msg.topic}")

    client = mqtt.Client()
    client.on_connect = _on_connect
    client.on_message = _on_message

    client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=30)

    if timeout_seconds:
        # Run for a limited time (useful for quick tests/demos)
        client.loop_start()
        time.sleep(timeout_seconds)
        client.loop_stop()
        client.disconnect()
    else:
        # Run forever (this is what the real orchestrator would do)
        client.loop_forever()


# ---------------------------------------------------------------------------
# DEMO: run this file directly to test publish + subscribe together
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import threading

    received_messages = []
    subscribed_event = threading.Event()  # signals "subscription is confirmed active"

    def handle_message(reading):
        print(f"RECEIVED: {reading}")
        received_messages.append(reading)

    def _on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(f"{TOPIC_PREFIX}/+/telemetry")
        else:
            print(f"Failed to connect, return code {rc}")

    def _on_subscribe(client, userdata, mid, granted_qos):
        # This fires ONLY once the broker has confirmed our subscription
        # is active — this is the moment it's actually safe to publish.
        print("Subscription confirmed by broker — safe to publish now.")
        subscribed_event.set()

    def _on_message(client, userdata, msg):
        try:
            reading = json.loads(msg.payload.decode())
            handle_message(reading)
        except json.JSONDecodeError:
            pass

    client = mqtt.Client()
    client.on_connect = _on_connect
    client.on_subscribe = _on_subscribe
    client.on_message = _on_message
    client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=30)
    client.loop_start()

    print("Waiting for subscription to be confirmed by the broker...")
    confirmed = subscribed_event.wait(timeout=10)  # wait up to 10s, don't guess with sleep()

    if not confirmed:
        print("Subscription was not confirmed in time — check your internet connection.")
    else:
        print("\nPublishing 3 test readings...")
        for i in range(3):
            fake_reading = {"node_id": "TEST1", "tick": i, "pm25": 12.5 + i, "co2": 500 + i * 10}
            publish_reading("TEST1", fake_reading)
            time.sleep(1)

        print("\nWaiting for messages to arrive...")
        time.sleep(3)

    client.loop_stop()
    client.disconnect()

    print(f"\nTotal messages received: {len(received_messages)}")
    if len(received_messages) == 3:
        print("SUCCESS — MQTT publish and subscribe both worked correctly.")
    else:
        print("Some messages may have been missed — this can happen on a public")
        print("test broker under load. Try running again, or check your internet connection.")