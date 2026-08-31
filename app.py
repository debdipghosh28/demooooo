import os
import json
import time
import queue
import threading
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
import xgboost as xgb
import model_trainer

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

app = Flask(__name__)

# Global model and metadata references
model = None
metadata = {}

# ---------------------------------------------------------------------------
# Hardware & Serial Port Manager (ESP32 & Arduino Uno)
# ---------------------------------------------------------------------------
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
        if not HAS_PYSERIAL:
            return []
        
        detected = []
        try:
            for p in serial.tools.list_ports.comports():
                desc = p.description or ""
                hwid = p.hwid or ""
                mfg = p.manufacturer or ""
                
                # Intelligent board/driver classification
                board_hint = "Standard Serial Device"
                hwid_upper = hwid.upper()
                desc_upper = desc.upper()
                
                if "1A86" in hwid_upper or "CH340" in desc_upper or "CH341" in desc_upper:
                    board_hint = "CH340 USB-Serial (ESP32 / Arduino Clone)"
                elif "10C4" in hwid_upper or "CP210" in desc_upper:
                    board_hint = "Silicon Labs CP210x (ESP32 NodeMCU)"
                elif "0403" in hwid_upper or "FTDI" in desc_upper or "FT232" in desc_upper:
                    board_hint = "FTDI USB Serial (Arduino / ESP32)"
                elif "2341" in hwid_upper or "ARDUINO" in desc_upper or "UNO" in desc_upper:
                    board_hint = "Arduino Uno (Official ATmega16U2)"
                elif "303A" in hwid_upper or "ESPRESSIF" in desc_upper or "ESP32" in desc_upper:
                    board_hint = "ESP32 Native USB CDC / JTAG"
                elif "BTHENUM" in hwid_upper or "BLUETOOTH" in desc_upper:
                    board_hint = "Bluetooth Serial Port"

                detected.append({
                    "port": p.device,
                    "description": desc,
                    "hwid": hwid,
                    "manufacturer": mfg,
                    "board_hint": board_hint
                })
        except Exception as e:
            print(f"[SerialManager] Error listing ports: {e}")
        return detected

    def connect(self, port, baud_rate=115200, board="ESP32"):
        if not HAS_PYSERIAL:
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
            except Exception as e:
                self.is_running = False
                self.ser = None
                return False, str(e)

    def disconnect(self):
        with self.lock:
            self.is_running = False
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            old_port = self.current_port
            self.current_port = None
        return True, f"Disconnected from {old_port or 'port'}"

    def send_command(self, command):
        with self.lock:
            if not self.ser or not self.is_running:
                return False, "Serial port not connected"
            try:
                self.ser.write((command.strip() + "\n").encode('utf-8'))
                return True, f"Command '{command}' sent"
            except Exception as e:
                return False, str(e)

    def get_status(self):
        with self.lock:
            return {
                "connected": self.is_running and self.ser is not None and self.ser.is_open,
                "port": self.current_port,
                "baud_rate": self.current_baud,
                "board": self.current_board,
                "packets_received": self.packets_count,
                "last_packet_time": self.last_packet_time,
                "last_raw_line": self.last_raw_line
            }

    def _reader_loop(self):
        global latest_esp32_telemetry
        while self.is_running and self.ser and self.ser.is_open:
            try:
                raw_bytes = self.ser.readline()
                if not raw_bytes:
                    continue
                line = raw_bytes.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                
                self.last_raw_line = line
                
                # Check if JSON formatted packet
                if line.startswith('{') and line.endswith('}'):
                    try:
                        data = json.loads(line)
                        now = time.time()
                        dev_id = data.get("device_id", f"{self.current_board}-PORT-{self.current_port}")
                        temp = float(data.get("temperature", data.get("Temperature", 37.0)))
                        hr = int(data.get("heart_rate", data.get("Heart_Rate", 75)))
                        spo2 = float(data.get("spo2", data.get("SpO2", 98.0)))
                        humidity = float(data.get("humidity", data.get("Humidity", 50.0)))
                        aqi = int(data.get("aqi", data.get("AQI", 100)))
                        bp = data.get("blood_pressure", data.get("Blood_Pressure", "Normal"))
                        board_name = data.get("board", self.current_board)
                        
                        if "fever_severity" in data:
                            fever_sev = data["fever_severity"]
                        elif temp < 37.3:
                            fever_sev = "Normal"
                        elif temp <= 38.0:
                            fever_sev = "Mild Fever"
                        else:
                            fever_sev = "High Fever"

                        with esp32_lock:
                            self.packets_count += 1
                            self.last_packet_time = now
                            
                            if dev_id not in registered_devices:
                                registered_devices[dev_id] = {
                                    "device_id": dev_id,
                                    "name": data.get("device_name", f"{board_name} on {self.current_port}"),
                                    "ip_address": self.current_port,
                                    "protocol": f"USB-Serial ({board_name})",
                                    "last_seen": now,
                                    "packets_received": 0,
                                    "online": True
                                }
                            dev_record = registered_devices[dev_id]
                            dev_record["last_seen"] = now
                            dev_record["packets_received"] = self.packets_count
                            dev_record["online"] = True
                            
                            latest_esp32_telemetry = {
                                "device_id": dev_id,
                                "device_name": data.get("device_name", f"{board_name} Medical Node"),
                                "board": board_name,
                                "status": "online",
                                "timestamp": now,
                                "temperature": round(temp, 1),
                                "fever_severity": fever_sev,
                                "heart_rate": hr,
                                "spo2": round(spo2, 1),
                                "humidity": round(humidity, 1),
                                "aqi": aqi,
                                "blood_pressure": bp,
                                "battery_mv": data.get("battery_mv", 4100),
                                "rssi": 0,
                                "packet_count": self.packets_count,
                                "protocol": "USB-Serial",
                                "port": self.current_port,
                                "symptoms": {
                                    "headache": data.get("headache", "No"),
                                    "body_ache": data.get("body_ache", "No"),
                                    "fatigue": data.get("fatigue", "No")
                                }
                            }
                        broadcast_esp32_telemetry(latest_esp32_telemetry)
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                time.sleep(0.1)

serial_manager = SerialPortManager()

# ---------------------------------------------------------------------------
# ESP32 & Arduino IoT Hub State & Real-time SSE Dispatcher
# ---------------------------------------------------------------------------
esp32_lock = threading.Lock()
esp32_listeners = []
esp32_command_queues = {} # device_id -> list of commands

# In-memory latest telemetry snapshot
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
    "symptoms": {
        "headache": "Yes",
        "body_ache": "No",
        "fatigue": "Yes"
    }
}

registered_devices = {
    "ESP32-DEMO-NODE": {
        "device_id": "ESP32-DEMO-NODE",
        "name": "Relivio Medical Node 1",
        "ip_address": "192.168.1.120",
        "protocol": "WiFi/BLE",
        "last_seen": time.time(),
        "packets_received": 1,
        "online": True
    }
}

def broadcast_esp32_telemetry(payload):
    """Pushes a new telemetry packet to all connected SSE browser listeners."""
    with esp32_lock:
        dead_listeners = []
        for q in esp32_listeners:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead_listeners.append(q)
            except Exception:
                dead_listeners.append(q)
        for dead in dead_listeners:
            if dead in esp32_listeners:
                esp32_listeners.remove(dead)

def init_model():
    global model, metadata
    model_path = os.path.join(os.path.dirname(__file__), "model.json")
    meta_path = os.path.join(os.path.dirname(__file__), "model_meta.json")
    
    if not os.path.exists(model_path) or not os.path.exists(meta_path):
        print("Training new model...")
        model_trainer.train_and_save_model()
    
    model = xgb.Booster()
    model.load_model(model_path)
    
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            metadata = json.load(f)
    print("Model and metadata initialized successfully.")

# Automatically initialize model on module import
init_model()

# Curated preset sample cases for fast demo & evaluation
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
            "Previous_Medication": "None"
        }
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
            "Previous_Medication": "Paracetamol"
        }
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
            "Previous_Medication": "None"
        }
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
            "Previous_Medication": "None"
        }
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
            "Previous_Medication": "None"
        }
    }
}

def generate_clinical_guidance(features, prediction, confidence):
    """
    Generates intelligent contextual clinical notes, dosage advice,
    and caution warnings based on patient parameters.
    """
    insights = []
    cautions = []
    
    temp = float(features.get('Temperature', 37.0))
    age = float(features.get('Age', 30))
    bp = features.get('Blood_Pressure', 'Normal')
    allergies = features.get('Allergies', 'No')
    chronic = features.get('Chronic_Conditions', 'No')
    body_ache = features.get('Body_Ache', 'No')
    headache = features.get('Headache', 'No')
    heart_rate = float(features.get('Heart_Rate', 75))
    aqi = float(features.get('AQI', 100))
    
    # Medication specifics
    if prediction == "Paracetamol":
        dosage = "Standard adult dose: 500mg - 1000mg every 4 to 6 hours as needed (Max: 4000mg / 24h)."
        mechanism = "Antipyretic and analgesic with central nervous system action. Gentle on gastric mucosa."
        if age < 12:
            insights.append("Pediatric dosage: 10-15 mg/kg per dose. Consult physician or pediatrician.")
        if chronic == "Yes":
            cautions.append("Monitor hepatic function. Do not combine with other acetaminophen-containing medications.")
    else:  # Ibuprofen
        dosage = "Standard adult dose: 200mg - 400mg every 6 to 8 hours with food (Max: 1200mg OTC / 24h)."
        mechanism = "Non-Steroidal Anti-Inflammatory Drug (NSAID) reducing prostaglandins, swelling, and high pyrexia."
        if bp == "High":
            cautions.append("Hypertension notice: NSAIDs can mildly elevate blood pressure. Take with caution or consult MD.")
        if allergies == "Yes" or chronic == "Yes":
            cautions.append("Caution: Take with meals to protect stomach lining. Avoid if history of peptic ulcer or aspirin allergy.")
        if age < 6:
            cautions.append("For young children, use pediatric oral suspensions under medical supervision.")

    # Fever & Vital Insights
    if temp >= 38.5:
        insights.append("High pyrexia (>38.5°C): Ensure active hydration, cold compresses, and monitor core temperature.")
    elif temp >= 37.3:
        insights.append("Low-grade fever (37.3°C - 38.0°C): Adequate bed rest and oral rehydration recommended.")
    else:
        insights.append("Normothermic (Normal temperature range). Maintain general wellness.")

    if body_ache == "Yes" or headache == "Yes":
        insights.append("Concurrent pain symptoms detected: Medication will assist with analgesic relief.")

    if heart_rate > 95:
        insights.append("Tachycardia / Elevated heart rate observed (>95 bpm). Common during fever; rest is advised.")
        
    if aqi > 200:
        insights.append("Poor ambient air quality (AQI > 200): Respiratory irritation may exacerbate fatigue. Stay indoors.")

    return {
        "dosage_info": dosage,
        "mechanism": mechanism,
        "clinical_insights": insights,
        "precautions": cautions
    }

@app.route('/')
def index():
    return render_template('index.html', metadata=metadata)

@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "No input data provided"}), 400
        
        # Run inference
        result = model_trainer.predict_single(model, data)
        
        # Clinical guidance generator
        guidance = generate_clinical_guidance(data, result['prediction'], result['confidence_percentage'])
        
        return jsonify({
            "success": True,
            "prediction": result['prediction'],
            "confidence_percentage": result['confidence_percentage'],
            "probabilities": result['probabilities'],
            "guidance": guidance,
            "input_summary": {
                "temperature": f"{data.get('Temperature')} °C",
                "fever_severity": data.get('Fever_Severity'),
                "age": data.get('Age'),
                "gender": data.get('Gender'),
                "bmi": data.get('BMI')
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sample-cases', methods=['GET'])
def get_sample_cases():
    return jsonify({"success": True, "cases": SAMPLE_CASES})

@app.route('/api/model-info', methods=['GET'])
def get_model_info():
    return jsonify({"success": True, "metadata": metadata})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "model_loaded": model is not None})

# ---------------------------------------------------------------------------
# ESP32 IoT API Endpoints (WiFi, Bluetooth gateway, Serial and SSE)
# ---------------------------------------------------------------------------

@app.route('/api/esp32/telemetry', methods=['POST'])
def receive_esp32_telemetry():
    """
    Ingests live telemetry packets from ESP32 over WiFi HTTP POST or IoT gateway.
    Payload Example:
    {
        "device_id": "ESP32-RELIVIO-01",
        "temperature": 38.4,
        "heart_rate": 92,
        "spo2": 97.5,
        "humidity": 58.0,
        "aqi": 120,
        "blood_pressure": "Normal",
        "headache": "Yes",
        "body_ache": "Yes",
        "fatigue": "Yes",
        "battery_mv": 4120,
        "rssi": -58
    }
    """
    global latest_esp32_telemetry
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "Missing JSON payload"}), 400

        dev_id = data.get("device_id", "ESP32-NODE-1")
        temp = float(data.get("temperature", data.get("Temperature", 37.0)))
        hr = int(data.get("heart_rate", data.get("Heart_Rate", 75)))
        spo2 = float(data.get("spo2", data.get("SpO2", 98.0)))
        humidity = float(data.get("humidity", data.get("Humidity", 50.0)))
        aqi = int(data.get("aqi", data.get("AQI", 100)))
        bp = data.get("blood_pressure", data.get("Blood_Pressure", "Normal"))

        # Determine fever severity automatically if not supplied
        if "fever_severity" in data:
            fever_sev = data["fever_severity"]
        elif temp < 37.3:
            fever_sev = "Normal"
        elif temp <= 38.0:
            fever_sev = "Mild Fever"
        else:
            fever_sev = "High Fever"

        now = time.time()
        with esp32_lock:
            # Update registered devices table
            if dev_id not in registered_devices:
                registered_devices[dev_id] = {
                    "device_id": dev_id,
                    "name": data.get("device_name", f"Relivio ESP32 ({dev_id})"),
                    "ip_address": request.remote_addr,
                    "protocol": data.get("protocol", "WiFi-HTTP"),
                    "last_seen": now,
                    "packets_received": 0,
                    "online": True
                }
            
            dev_record = registered_devices[dev_id]
            dev_record["last_seen"] = now
            dev_record["packets_received"] = dev_record.get("packets_received", 0) + 1
            dev_record["ip_address"] = request.remote_addr
            dev_record["online"] = True

            packet_count = dev_record["packets_received"]

            latest_esp32_telemetry = {
                "device_id": dev_id,
                "status": "online",
                "timestamp": now,
                "temperature": round(temp, 1),
                "fever_severity": fever_sev,
                "heart_rate": hr,
                "spo2": round(spo2, 1),
                "humidity": round(humidity, 1),
                "aqi": aqi,
                "blood_pressure": bp,
                "battery_mv": data.get("battery_mv", 4000),
                "rssi": data.get("rssi", -60),
                "packet_count": packet_count,
                "symptoms": {
                    "headache": data.get("headache", "No"),
                    "body_ache": data.get("body_ache", "No"),
                    "fatigue": data.get("fatigue", "No")
                }
            }

        # Broadcast to all open web dashboard SSE connections
        broadcast_esp32_telemetry(latest_esp32_telemetry)

        # Check if there are any pending commands for this device
        commands_to_send = []
        with esp32_lock:
            if dev_id in esp32_command_queues and esp32_command_queues[dev_id]:
                commands_to_send = esp32_command_queues[dev_id]
                esp32_command_queues[dev_id] = []

        return jsonify({
            "success": True,
            "message": "Telemetry received & distributed",
            "server_time": now,
            "commands": commands_to_send
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/esp32/latest', methods=['GET'])
def get_latest_esp32_telemetry():
    """Returns the most recent cached telemetry reading."""
    with esp32_lock:
        is_fresh = (time.time() - latest_esp32_telemetry.get("timestamp", 0)) < 15
        result = dict(latest_esp32_telemetry)
        result["is_fresh"] = is_fresh
        return jsonify({"success": True, "data": result})

@app.route('/api/esp32/stream')
def stream_esp32_telemetry():
    """
    Server-Sent Events (SSE) stream allowing the frontend to receive
    live ESP32 telemetry events in real-time with zero polling overhead.
    """
    def event_stream():
        q = queue.Queue(maxsize=100)
        with esp32_lock:
            esp32_listeners.append(q)
            # Push initial current state immediately upon connecting
            init_data = json.dumps(latest_esp32_telemetry)
        
        yield f"event: connected\ndata: {{\"connected\": true, \"timestamp\": {time.time()}}}\n\n"
        yield f"event: telemetry\ndata: {init_data}\n\n"
        
        try:
            while True:
                try:
                    # Wait for next telemetry item with 15s heartbeat timeout
                    item = q.get(timeout=15.0)
                    yield f"event: telemetry\ndata: {json.dumps(item)}\n\n"
                except queue.Empty:
                    # Send periodic keepalive heartbeat ping
                    yield f": heartbeat {time.time()}\n\n"
        except GeneratorExit:
            with esp32_lock:
                if q in esp32_listeners:
                    esp32_listeners.remove(q)

    return Response(event_stream(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    })

@app.route('/api/esp32/command', methods=['POST'])
def send_esp32_command():
    """
    Queues a command for an ESP32 device or broadcasts command to all.
    Supported commands: 'SAMPLE_NOW', 'LED_TOGGLE', 'BEEP', 'CALIBRATE', 'RESET'.
    """
    try:
        req = request.get_json(force=True)
        command = req.get("command", "").strip().upper()
        target_device = req.get("device_id", "all")
        
        if not command:
            return jsonify({"success": False, "error": "Command parameter required"}), 400

        with esp32_lock:
            if target_device == "all":
                for dev_id in registered_devices:
                    if dev_id not in esp32_command_queues:
                        esp32_command_queues[dev_id] = []
                    esp32_command_queues[dev_id].append({"cmd": command, "time": time.time()})
            else:
                if target_device not in esp32_command_queues:
                    esp32_command_queues[target_device] = []
                esp32_command_queues[target_device].append({"cmd": command, "time": time.time()})

        # Also push command event over SSE to connected browser clients
        broadcast_esp32_telemetry({
            "type": "command_dispatched",
            "command": command,
            "target": target_device,
            "timestamp": time.time()
        })

        return jsonify({
            "success": True,
            "message": f"Command '{command}' queued for device(s) '{target_device}'"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/esp32/proxy', methods=['GET'])
def proxy_esp32_request():
    """
    CORS-safe proxy to fetch data directly from a local ESP32 IP webserver.
    Example: /api/esp32/proxy?target=http://192.168.1.105/vitals
    """
    target_url = request.args.get('target', '')
    if not target_url or not (target_url.startswith('http://') or target_url.startswith('https://')):
        return jsonify({"success": False, "error": "Invalid or missing 'target' URL parameter"}), 400

    try:
        req = urllib.request.Request(target_url, headers={'User-Agent': 'Relivio-Backend-Proxy/1.0'})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            content = resp.read().decode('utf-8')
            try:
                json_data = json.loads(content)
                return jsonify({"success": True, "data": json_data})
            except ValueError:
                return jsonify({"success": True, "raw": content})
    except Exception as err:
        return jsonify({"success": False, "error": f"Failed to reach ESP32 at {target_url}: {str(err)}"}), 502

@app.route('/api/esp32/devices', methods=['GET'])
def get_esp32_devices():
    """Returns list of registered ESP32 hardware devices."""
    now = time.time()
    with esp32_lock:
        device_list = []
        for dev_id, info in registered_devices.items():
            item = dict(info)
            item["online"] = (now - item.get("last_seen", 0)) < 30
            device_list.append(item)
        return jsonify({"success": True, "devices": device_list})

@app.route('/api/firmware/<path:filename>', methods=['GET'])
def download_firmware(filename):
    """Allows downloading the pre-built ready-to-flash ESP32 & Arduino sketches."""
    firmware_dir = os.path.join(app.static_folder, 'firmware')
    if not os.path.exists(firmware_dir):
        os.makedirs(firmware_dir, exist_ok=True)
    return send_from_directory(firmware_dir, filename, as_attachment=True)

# ---------------------------------------------------------------------------
# Serial Port Management API (ESP32 & Arduino Uno)
# ---------------------------------------------------------------------------

@app.route('/api/serial/ports', methods=['GET'])
def get_serial_ports():
    """Returns all active COM ports on the system with detected board types."""
    ports = serial_manager.list_ports()
    return jsonify({
        "success": True,
        "ports": ports,
        "count": len(ports),
        "pyserial_available": HAS_PYSERIAL
    })

@app.route('/api/serial/connect', methods=['POST'])
def connect_serial_port():
    """Connects to a COM port at the specified baud rate."""
    data = request.get_json(force=True) or {}
    port = data.get('port')
    baud_rate = data.get('baud_rate', 115200)
    board = data.get('board', 'ESP32')

    if not port:
        return jsonify({"success": False, "error": "Missing 'port' parameter (e.g., 'COM3')"}), 400

    success, message = serial_manager.connect(port, baud_rate, board)
    if success:
        return jsonify({
            "success": True,
            "message": message,
            "status": serial_manager.get_status()
        })
    else:
        return jsonify({"success": False, "error": message}), 500

@app.route('/api/serial/disconnect', methods=['POST'])
def disconnect_serial_port():
    """Disconnects the active backend serial port."""
    success, message = serial_manager.disconnect()
    return jsonify({
        "success": success,
        "message": message,
        "status": serial_manager.get_status()
    })

@app.route('/api/serial/status', methods=['GET'])
def get_serial_status():
    """Returns the current connection status of the backend serial port."""
    return jsonify({
        "success": True,
        "status": serial_manager.get_status(),
        "pyserial_available": HAS_PYSERIAL
    })

@app.route('/api/serial/send', methods=['POST'])
def send_serial_command():
    """Sends a text command over the active serial port."""
    data = request.get_json(force=True) or {}
    command = data.get('command')
    if not command:
        return jsonify({"success": False, "error": "Missing 'command' parameter"}), 400

    success, message = serial_manager.send_command(command)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "error": message}), 500

if __name__ == '__main__':
    init_model()
    app.run(host='0.0.0.0', port=5000, debug=True)

