import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request

import xgboost as xgb
from flask import Flask, Response, jsonify, render_template, request, send_from_directory

import model_trainer

try:
    import serial
    import serial.tools.list_ports

    HAS_PYSERIAL = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PYSERIAL = False
    serial = None

app = Flask(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.json")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "model_meta.json")

model = None
metadata = {}

esp32_lock = threading.Lock()
esp32_listeners = []
esp32_command_queues = {}
registered_devices = {
    "ESP32-DEMO-NODE": {
        "device_id": "ESP32-DEMO-NODE",
        "name": "Relivio Medical Node 1",
        "ip_address": "192.168.1.120",
        "protocol": "WiFi/BLE",
        "last_seen": time.time(),
        "packets_received": 1,
        "online": True,
    }
}
latest_esp32_telemetry = {
    "device_id": "ESP32-DEMO-NODE",
    "status": "online",
    "timestamp": time.time(),
    "temperature": 37.7,
    "fever_severity": "Mild Fever",
    "heart_rate": 78,
    "spo2": 98.5,
    "humidity": 55.0,
    "aqi": 110,
    "blood_pressure": "Normal",
    "battery_mv": 3950,
    "rssi": -62,
    "packet_count": 1,
    "symptoms": {"headache": "Yes", "body_ache": "No", "fatigue": "Yes"},
}

SAMPLE_CASES = {
    "mild_fever": {
        "title": "Mild Viral Fever (Young Adult)",
        "description": "Patient experiencing moderate temperature elevation (37.7°C), headache, and fatigue.",
        "data": {
            "Temperature": 37.7,
            "Fever_Severity": "Mild Fever",
            "Age": 28,
            "Gender": "Female",
            "BMI": 22.4,
            "Headache": "Yes",
            "Body_Ache": "No",
            "Fatigue": "Yes",
            "Chronic_Conditions": "No",
            "Allergies": "No",
            "Smoking_History": "No",
            "Alcohol_Consumption": "No",
            "Humidity": 55.0,
            "AQI": 110,
            "Physical_Activity": "Moderate",
            "Diet_Type": "Vegetarian",
            "Heart_Rate": 78,
            "Blood_Pressure": "Normal",
            "Previous_Medication": "None",
        },
    },
    "high_fever_body_ache": {
        "title": "High Fever with Acute Body Ache",
        "description": "Severe fever (39.2°C) with significant inflammatory pain and body ache.",
        "data": {
            "Temperature": 39.2,
            "Fever_Severity": "High Fever",
            "Age": 38,
            "Gender": "Male",
            "BMI": 25.8,
            "Headache": "Yes",
            "Body_Ache": "Yes",
            "Fatigue": "Yes",
            "Chronic_Conditions": "No",
            "Allergies": "No",
            "Smoking_History": "No",
            "Alcohol_Consumption": "No",
            "Humidity": 68.0,
            "AQI": 160,
            "Physical_Activity": "Active",
            "Diet_Type": "Non-Vegetarian",
            "Heart_Rate": 94,
            "Blood_Pressure": "Normal",
            "Previous_Medication": "Paracetamol",
        },
    },
    "pediatric_mild": {
        "title": "Pediatric Case (Child with Low-Grade Fever)",
        "description": "Child (Age 8) presenting with mild fever (37.5°C) and fatigue.",
        "data": {
            "Temperature": 37.5,
            "Fever_Severity": "Mild Fever",
            "Age": 8,
            "Gender": "Male",
            "BMI": 19.2,
            "Headache": "No",
            "Body_Ache": "No",
            "Fatigue": "Yes",
            "Chronic_Conditions": "No",
            "Allergies": "No",
            "Smoking_History": "No",
            "Alcohol_Consumption": "No",
            "Humidity": 60.0,
            "AQI": 85,
            "Physical_Activity": "Active",
            "Diet_Type": "Vegetarian",
            "Heart_Rate": 88,
            "Blood_Pressure": "Normal",
            "Previous_Medication": "None",
        },
    },
    "elderly_chronic": {
        "title": "Elderly Patient with Hypertension & High Fever",
        "description": "Senior patient (Age 72) with high fever (38.8°C), hypertension, and chronic conditions.",
        "data": {
            "Temperature": 38.8,
            "Fever_Severity": "High Fever",
            "Age": 72,
            "Gender": "Female",
            "BMI": 28.5,
            "Headache": "Yes",
            "Body_Ache": "Yes",
            "Fatigue": "Yes",
            "Chronic_Conditions": "Yes",
            "Allergies": "Yes",
            "Smoking_History": "No",
            "Alcohol_Consumption": "No",
            "Humidity": 48.0,
            "AQI": 210,
            "Physical_Activity": "Sedentary",
            "Diet_Type": "Vegetarian",
            "Heart_Rate": 86,
            "Blood_Pressure": "High",
            "Previous_Medication": "None",
        },
    },
    "normal_baseline": {
        "title": "Normal Baseline (No Fever)",
        "description": "Standard normal physiological baseline check (36.6°C).",
        "data": {
            "Temperature": 36.6,
            "Fever_Severity": "Normal",
            "Age": 24,
            "Gender": "Female",
            "BMI": 21.3,
            "Headache": "No",
            "Body_Ache": "No",
            "Fatigue": "No",
            "Chronic_Conditions": "No",
            "Allergies": "No",
            "Smoking_History": "No",
            "Alcohol_Consumption": "No",
            "Humidity": 50.0,
            "AQI": 65,
            "Physical_Activity": "Moderate",
            "Diet_Type": "Vegan",
            "Heart_Rate": 72,
            "Blood_Pressure": "Normal",
            "Previous_Medication": "None",
        },
    },
}


def infer_fever_severity(temp):
    if temp < 37.3:
        return "Normal"
    if temp <= 38.0:
        return "Mild Fever"
    return "High Fever"


def broadcast_esp32_telemetry(payload):
    """Push payloads to all connected SSE listeners."""
    with esp32_lock:
        dead = []
        for listener in esp32_listeners:
            try:
                listener.put_nowait(payload)
            except queue.Full:
                dead.append(listener)
            except Exception:
                dead.append(listener)
        for stale in dead:
            if stale in esp32_listeners:
                esp32_listeners.remove(stale)


def init_model():
    global model, metadata

    if not os.path.exists(MODEL_PATH) or not os.path.exists(METADATA_PATH):
        print("[app] Training missing model files...")
        model_trainer.train_and_save_model()

    model = xgb.Booster()
    model.load_model(MODEL_PATH)

    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)

    print("[app] Model initialized successfully.")


def normalize_telemetry_payload(data, source="http", port=None, board=None):
    if not isinstance(data, dict):
        return None

    try:
        temperature = float(data.get("temperature", data.get("Temperature", 37.0)))
        heart_rate = int(data.get("heart_rate", data.get("Heart_Rate", 75)))
        spo2 = float(data.get("spo2", data.get("SpO2", 98.0)))
        humidity = float(data.get("humidity", data.get("Humidity", 50.0)))
        aqi = int(data.get("aqi", data.get("AQI", 100)))
        blood_pressure = data.get("blood_pressure", data.get("Blood_Pressure", "Normal"))
        device_id = data.get("device_id", data.get("deviceId", "ESP32-NODE-1"))
        device_name = data.get("device_name", data.get("deviceName", f"Relivio {board or 'ESP32'} Node"))
    except (TypeError, ValueError):
        return None

    fever_severity = data.get("fever_severity") or infer_fever_severity(temperature)
    payload = {
        "device_id": str(device_id),
        "device_name": str(device_name),
        "board": data.get("board", board or "ESP32"),
        "status": "online",
        "timestamp": time.time(),
        "temperature": round(temperature, 1),
        "fever_severity": fever_severity,
        "heart_rate": heart_rate,
        "spo2": round(spo2, 1),
        "humidity": round(humidity, 1),
        "aqi": aqi,
        "blood_pressure": blood_pressure,
        "battery_mv": int(data.get("battery_mv", data.get("battery", 4000))),
        "rssi": int(data.get("rssi", -60)),
        "packet_count": 0,
        "protocol": data.get("protocol", "wifi" if source == "http" else "serial"),
        "port": port,
        "symptoms": {
            "headache": data.get("headache", data.get("symptoms", {}).get("headache", "No")),
            "body_ache": data.get("body_ache", data.get("symptoms", {}).get("body_ache", "No")),
            "fatigue": data.get("fatigue", data.get("symptoms", {}).get("fatigue", "No")),
        },
    }

    return payload


def update_live_telemetry(payload):
    global latest_esp32_telemetry
    if not payload:
        return

    now = time.time()
    payload["timestamp"] = now
    payload["status"] = "online"

    device_id = payload.get("device_id", "ESP32-NODE-1")
    with esp32_lock:
        if device_id not in registered_devices:
            registered_devices[device_id] = {
                "device_id": device_id,
                "name": payload.get("device_name", device_id),
                "ip_address": payload.get("port") or "unknown",
                "protocol": payload.get("protocol", "WiFi/BLE"),
                "last_seen": now,
                "packets_received": 0,
                "online": True,
            }

        device = registered_devices[device_id]
        device["last_seen"] = now
        device["packets_received"] = int(device.get("packets_received", 0)) + 1
        device["ip_address"] = payload.get("port") or device.get("ip_address", "unknown")
        device["online"] = True
        payload["packet_count"] = device["packets_received"]

        latest_esp32_telemetry = payload.copy()
        latest_esp32_telemetry["packet_count"] = payload["packet_count"]

    broadcast_esp32_telemetry(latest_esp32_telemetry)


def generate_clinical_guidance(features, prediction):
    insights = []
    cautions = []

    temp = float(features.get("Temperature", 37.0))
    age = float(features.get("Age", 30))
    bp = features.get("Blood_Pressure", "Normal")
    allergies = features.get("Allergies", "No")
    chronic = features.get("Chronic_Conditions", "No")
    body_ache = features.get("Body_Ache", "No")
    headache = features.get("Headache", "No")
    heart_rate = float(features.get("Heart_Rate", 75))
    aqi = float(features.get("AQI", 100))

    if prediction == "Paracetamol":
        dosage = "Standard adult dose: 500mg - 1000mg every 4 to 6 hours as needed (max 4000mg / 24h)."
        mechanism = "Antipyretic and analgesic with central nervous system action. Gentle on the stomach."
        if age < 12:
            insights.append("Pediatric dosing: 10-15 mg/kg per dose, with physician guidance.")
        if chronic == "Yes":
            cautions.append("Monitor liver function and avoid combining with other acetaminophen products.")
    else:
        dosage = "Standard adult dose: 200mg - 400mg every 6 to 8 hours with food (max 1200mg OTC / 24h)."
        mechanism = "NSAID that reduces inflammation and helps relieve fever and pain."
        if bp == "High":
            cautions.append("NSAIDs can mildly raise blood pressure; seek advice when hypertensive.")
        if allergies == "Yes" or chronic == "Yes":
            cautions.append("Use with meals and avoid if there is a history of peptic ulcer or aspirin sensitivity.")
        if age < 6:
            cautions.append("Pediatric ibuprofen dosing should be guided by a clinician or safe weight-based instructions.")

    if temp >= 38.5:
        insights.append("High pyrexia (>38.5°C): maintain hydration and monitor temperature closely.")
    elif temp >= 37.3:
        insights.append("Low-grade fever (37.3°C - 38.0°C): rest and oral rehydration are recommended.")
    else:
        insights.append("Temperature is within the normal range; maintain routine wellness care.")

    if body_ache == "Yes" or headache == "Yes":
        insights.append("Pain symptoms are present; the recommended medication should help with analgesic relief.")
    if heart_rate > 95:
        insights.append("Heart rate is elevated (>95 bpm), which may be consistent with fever or stress.")
    if aqi > 200:
        insights.append("Ambient air quality is poor; consider reducing exposure and staying hydrated.")

    return {
        "dosage_info": dosage,
        "mechanism": mechanism,
        "clinical_insights": insights,
        "precautions": cautions,
    }


class SerialPortManager:
    def __init__(self):
        self.ser = None
        self.is_running = False
        self.thread = None
        self.current_port = None
        self.current_baud = 115200
        self.current_board = "ESP32"
        self.lock = threading.Lock()
        self.packets_count = 0
        self.last_packet_time = 0
        self.last_raw_line = ""

    def list_ports(self):
        if not HAS_PYSERIAL or serial is None:
            return []

        ports = []
        try:
            for port in serial.tools.list_ports.comports():
                desc = port.description or ""
                hwid = port.hwid or ""
                manufacturer = port.manufacturer or ""
                hint = "Standard Serial Device"
                upper_desc = desc.upper()
                upper_hwid = hwid.upper()

                if "1A86" in upper_hwid or "CH340" in upper_desc or "CH341" in upper_desc:
                    hint = "CH340 USB-Serial (ESP32 / Arduino Clone)"
                elif "10C4" in upper_hwid or "CP210" in upper_desc:
                    hint = "Silicon Labs CP210x (ESP32 NodeMCU)"
                elif "0403" in upper_hwid or "FTDI" in upper_desc or "FT232" in upper_desc:
                    hint = "FTDI USB Serial (Arduino / ESP32)"
                elif "2341" in upper_hwid or "ARDUINO" in upper_desc or "UNO" in upper_desc:
                    hint = "Arduino Uno (Official ATmega16U2)"
                elif "303A" in upper_hwid or "ESPRESSIF" in upper_desc or "ESP32" in upper_desc:
                    hint = "ESP32 Native USB CDC / JTAG"
                elif "BTHENUM" in upper_hwid or "BLUETOOTH" in upper_desc:
                    hint = "Bluetooth Serial Port"

                ports.append({
                    "port": port.device,
                    "description": desc,
                    "hwid": hwid,
                    "manufacturer": manufacturer,
                    "board_hint": hint,
                })
        except Exception as exc:  # pragma: no cover - platform-specific
            print(f"[SerialManager] Error listing ports: {exc}")
        return ports

    def connect(self, port, baud_rate=115200, board="ESP32"):
        if not HAS_PYSERIAL or serial is None:
            return False, "pyserial module is not installed"

        with self.lock:
            if self.is_running:
                self.disconnect()

            try:
                self.ser = serial.Serial(port, int(baud_rate), timeout=1.0)
                self.current_port = port
                self.current_baud = int(baud_rate)
                self.current_board = board
                self.is_running = True
                self.packets_count = 0
                self.thread = threading.Thread(target=self._reader_loop, daemon=True)
                self.thread.start()
                return True, f"Connected to {port} at {baud_rate} baud ({board})"
            except Exception as exc:
                self.is_running = False
                self.ser = None
                return False, str(exc)

    def disconnect(self):
        with self.lock:
            self.is_running = False
            old_port = self.current_port
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            self.current_port = None
        return True, f"Disconnected from {old_port or 'port'}"

    def send_command(self, command):
        with self.lock:
            if not self.ser or not self.is_running:
                return False, "Serial port not connected"
            try:
                self.ser.write((command.strip() + "\n").encode("utf-8"))
                return True, f"Command '{command}' sent"
            except Exception as exc:
                return False, str(exc)

    def get_status(self):
        with self.lock:
            return {
                "connected": self.is_running and self.ser is not None and self.ser.is_open,
                "port": self.current_port,
                "baud_rate": self.current_baud,
                "board": self.current_board,
                "packets_received": self.packets_count,
                "last_packet_time": self.last_packet_time,
                "last_raw_line": self.last_raw_line,
            }

    def _reader_loop(self):
        while self.is_running and self.ser and self.ser.is_open:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                self.last_raw_line = line
                if line.startswith("[TX]"):
                    line = line[4:].strip()

                if line.startswith("{") and line.endswith("}"):
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    payload = normalize_telemetry_payload(payload, source="serial", port=self.current_port, board=self.current_board)
                    if payload is None:
                        continue

                    self.packets_count += 1
                    self.last_packet_time = time.time()
                    payload["packet_count"] = self.packets_count
                    update_live_telemetry(payload)
            except Exception:
                time.sleep(0.1)


serial_manager = SerialPortManager()


@app.route("/")
def index():
    return render_template("index.html", metadata=metadata)


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "model_loaded": model is not None})


@app.route("/api/model-info", methods=["GET"])
def get_model_info():
    return jsonify({"success": True, "metadata": metadata})


@app.route("/api/sample-cases", methods=["GET"])
def get_sample_cases():
    return jsonify({"success": True, "cases": SAMPLE_CASES})


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True) or {}
    if not data:
        return jsonify({"success": False, "error": "No input data provided"}), 400

    try:
        result = model_trainer.predict_single(model, data)
        guidance = generate_clinical_guidance(data, result["prediction"])
        return jsonify({
            "success": True,
            "prediction": result["prediction"],
            "confidence_percentage": result["confidence_percentage"],
            "probabilities": result["probabilities"],
            "guidance": guidance,
            "input_summary": {
                "temperature": f"{data.get('Temperature', 37.0)} °C",
                "fever_severity": data.get("Fever_Severity"),
                "age": data.get("Age"),
                "gender": data.get("Gender"),
                "bmi": data.get("BMI"),
            },
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/esp32/telemetry", methods=["POST"])
def receive_esp32_telemetry():
    data = request.get_json(force=True) or {}
    if not data:
        return jsonify({"success": False, "error": "Missing JSON payload"}), 400

    payload = normalize_telemetry_payload(data, source="http", port=request.remote_addr, board=data.get("board", "ESP32"))
    if payload is None:
        return jsonify({"success": False, "error": "Unable to parse telemetry payload"}), 400

    update_live_telemetry(payload)

    commands = []
    with esp32_lock:
        device_id = payload.get("device_id")
        if device_id in esp32_command_queues and esp32_command_queues[device_id]:
            commands = esp32_command_queues[device_id]
            esp32_command_queues[device_id] = []

    return jsonify({
        "success": True,
        "message": "Telemetry received & distributed",
        "server_time": time.time(),
        "commands": commands,
    })


@app.route("/api/esp32/latest", methods=["GET"])
def get_latest_esp32_telemetry():
    with esp32_lock:
        result = dict(latest_esp32_telemetry)
        result["is_fresh"] = (time.time() - result.get("timestamp", 0)) < 15
    return jsonify({"success": True, "data": result})


@app.route("/api/esp32/stream")
def stream_esp32_telemetry():
    def event_stream():
        queue_item = queue.Queue(maxsize=100)
        with esp32_lock:
            esp32_listeners.append(queue_item)
            initial_payload = json.dumps(latest_esp32_telemetry)

        yield f"event: connected\ndata: {{\"connected\": true, \"timestamp\": {time.time()}}}\n\n"
        yield f"event: telemetry\ndata: {initial_payload}\n\n"

        try:
            while True:
                try:
                    item = queue_item.get(timeout=15.0)
                    yield f"event: telemetry\ndata: {json.dumps(item)}\n\n"
                except queue.Empty:
                    yield f": heartbeat {time.time()}\n\n"
        except GeneratorExit:
            with esp32_lock:
                if queue_item in esp32_listeners:
                    esp32_listeners.remove(queue_item)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.route("/api/esp32/command", methods=["POST"])
def send_esp32_command():
    data = request.get_json(force=True) or {}
    command = str(data.get("command", "")).strip().upper()
    target_device = data.get("device_id", "all")

    if not command:
        return jsonify({"success": False, "error": "Command parameter required"}), 400

    with esp32_lock:
        if target_device == "all":
            for device_id in list(registered_devices.keys()):
                esp32_command_queues.setdefault(device_id, []).append({"cmd": command, "time": time.time()})
        else:
            esp32_command_queues.setdefault(target_device, []).append({"cmd": command, "time": time.time()})

    broadcast_esp32_telemetry({
        "type": "command_dispatched",
        "command": command,
        "target": target_device,
        "timestamp": time.time(),
    })

    return jsonify({"success": True, "message": f"Command '{command}' queued for device(s) '{target_device}'"})


@app.route("/api/esp32/proxy", methods=["GET"])
def proxy_esp32_request():
    target_url = request.args.get("target", "")
    if not target_url or not (target_url.startswith("http://") or target_url.startswith("https://")):
        return jsonify({"success": False, "error": "Invalid or missing 'target' URL parameter"}), 400

    try:
        req = urllib.request.Request(target_url, headers={"User-Agent": "Relivio-Backend-Proxy/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as response:
            content = response.read().decode("utf-8")
            try:
                return jsonify({"success": True, "data": json.loads(content)})
            except json.JSONDecodeError:
                return jsonify({"success": True, "raw": content})
    except Exception as exc:
        return jsonify({"success": False, "error": f"Failed to reach ESP32 at {target_url}: {exc}"}), 502


@app.route("/api/esp32/devices", methods=["GET"])
def get_esp32_devices():
    now = time.time()
    with esp32_lock:
        devices = []
        for info in registered_devices.values():
            item = dict(info)
            item["online"] = (now - item.get("last_seen", 0)) < 30
            devices.append(item)
    return jsonify({"success": True, "devices": devices})


@app.route("/api/firmware/<path:filename>", methods=["GET"])
def download_firmware(filename):
    static_dir = app.static_folder or os.path.join(os.path.dirname(__file__), "static")
    firmware_dir = os.path.join(static_dir, "esp32_relivio_firmware")
    if not os.path.exists(firmware_dir):
        os.makedirs(firmware_dir, exist_ok=True)
    return send_from_directory(firmware_dir, filename, as_attachment=True)


@app.route("/api/serial/ports", methods=["GET"])
def get_serial_ports():
    return jsonify({
        "success": True,
        "ports": serial_manager.list_ports(),
        "count": len(serial_manager.list_ports()),
        "pyserial_available": HAS_PYSERIAL,
    })


@app.route("/api/serial/connect", methods=["POST"])
def connect_serial_port():
    data = request.get_json(force=True) or {}
    port = data.get("port")
    baud_rate = data.get("baud_rate", 115200)
    board = data.get("board", "ESP32")

    if not port:
        return jsonify({"success": False, "error": "Missing 'port' parameter"}), 400

    success, message = serial_manager.connect(port, baud_rate, board)
    if success:
        return jsonify({"success": True, "message": message, "status": serial_manager.get_status()})
    return jsonify({"success": False, "error": message}), 500


@app.route("/api/serial/disconnect", methods=["POST"])
def disconnect_serial_port():
    success, message = serial_manager.disconnect()
    return jsonify({"success": success, "message": message, "status": serial_manager.get_status()})


@app.route("/api/serial/status", methods=["GET"])
def get_serial_status():
    return jsonify({"success": True, "status": serial_manager.get_status(), "pyserial_available": HAS_PYSERIAL})


@app.route("/api/serial/send", methods=["POST"])
def send_serial_command():
    data = request.get_json(force=True) or {}
    command = data.get("command")
    if not command:
        return jsonify({"success": False, "error": "Missing 'command' parameter"}), 400

    success, message = serial_manager.send_command(command)
    if success:
        return jsonify({"success": True, "message": message})
    return jsonify({"success": False, "error": message}), 500


init_model()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

