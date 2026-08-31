"""
Relivio MedPredict - ESP32 MicroPython Client
Flash to your ESP32 running MicroPython firmware (as main.py or run via Thonny)
"""

import time
import json
import urequests
import network
from machine import Pin

# --- Configuration ---
WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASS = "YOUR_WIFI_PASSWORD"
SERVER_URL = "http://192.168.1.6:5000/api/esp32/telemetry"

led = Pin(2, Pin.OUT)
led.value(0)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Connecting to WiFi '{WIFI_SSID}'...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        attempts = 0
        while not wlan.isconnected() and attempts < 20:
            led.value(not led.value())
            time.sleep(0.5)
            attempts += 1
            
    if wlan.isconnected():
        led.value(1)
        print("Connected! IP Config:", wlan.ifconfig())
        return True
    else:
        print("Failed to connect to WiFi")
        return False

def main():
    if not connect_wifi():
        return

    # Base vitals state
    temp = 37.8
    hr = 82
    spo2 = 98.2

    while True:
        try:
            payload = {
                "device_id": "ESP32-MPY-NODE",
                "device_name": "Relivio MicroPython ESP32",
                "temperature": round(temp, 1),
                "heart_rate": hr,
                "spo2": round(spo2, 1),
                "humidity": 55.0,
                "aqi": 110,
                "blood_pressure": "Normal",
                "headache": "Yes",
                "body_ache": "No",
                "fatigue": "Yes",
                "battery_mv": 4120,
                "protocol": "MicroPython-HTTP"
            }

            headers = {'Content-Type': 'application/json'}
            response = urequests.post(SERVER_URL, json=payload, headers=headers)
            print("Server Response:", response.status_code, response.text)
            response.close()

        except Exception as e:
            print("Error pushing telemetry:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
