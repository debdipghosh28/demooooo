"""
Relivio MedPredict - ESP32 Software Simulator & Telemetry Test Script
Simulates an ESP32 microcontroller streaming live medical vitals to the Flask backend.
"""

import time
import json
import random
import urllib.request
import urllib.error

SERVER_URL = "http://127.0.0.1:5000/api/esp32/telemetry"

device_state = {
    "device_id": "ESP32-VIRTUAL-NODE",
    "device_name": "Virtual Medical Sensor",
    "temperature": 37.8,
    "fever_severity": "Mild Fever",
    "heart_rate": 84,
    "spo2": 98.0,
    "humidity": 56.0,
    "aqi": 105,
    "blood_pressure": "Normal",
    "headache": "Yes",
    "body_ache": "No",
    "fatigue": "Yes",
    "battery_mv": 4150,
    "rssi": -55,
    "protocol": "Python-Sim"
}

print("=" * 60)
print("  Relivio ESP32 Virtual Telemetry Transmitter")
print(f"  Target: {SERVER_URL}")
print("  Press Ctrl+C to stop")
print("=" * 60)

packet_num = 1
while True:
    try:
        # Simulate slight physiological jitter
        device_state["temperature"] = round(device_state["temperature"] + random.uniform(-0.1, 0.1), 1)
        device_state["heart_rate"] = int(device_state["heart_rate"] + random.randint(-1, 1))
        device_state["spo2"] = round(min(100.0, max(94.0, device_state["spo2"] + random.uniform(-0.1, 0.1))), 1)

        payload = json.dumps(device_state).encode("utf-8")
        req = urllib.request.Request(
            SERVER_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[Packet #{packet_num:03d}] Sent | Temp: {device_state['temperature']}°C | HR: {device_state['heart_rate']} BPM | SpO2: {device_state['spo2']}% | Server: {data.get('message')}")
            if data.get("commands"):
                print(f"  >>> Received Remote Command: {data.get('commands')}")

        packet_num += 1
        time.sleep(2)

    except urllib.error.URLError as e:
        print(f"[Offline] Could not connect to Flask server ({e.reason}). Make sure 'python app.py' is running.")
        time.sleep(3)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
        break
