/**
 * ==================================================================================
 * Relivio MedPredict - ESP32 IoT Connectivity & Real-time Telemetry Engine
 * Supports: Web Bluetooth (BLE), WiFi (SSE & Direct REST), Web Serial (USB),
 * Virtual Hardware Simulator, and Dynamic ECG Waveform Visualizer.
 * ==================================================================================
 */

class RelivioESP32Hub {
    constructor() {
        // Active mode: 'none' | 'ble' | 'wifi' | 'serial' | 'simulator'
        this.activeMode = 'none';
        this.connectionStatus = 'disconnected'; // 'disconnected' | 'connecting' | 'connected' | 'error'
        
        // BLE handles
        this.bleDevice = null;
        this.bleServer = null;
        this.bleTelemetryChar = null;
        this.bleCommandChar = null;

        // Serial handles
        this.serialPort = null;
        this.serialReader = null;
        this.serialWriter = null;
        this.serialKeepReading = false;

        // WiFi handles
        this.eventSource = null;
        this.wifiPollInterval = null;
        this.wifiTargetIp = '192.168.1.100';

        // Simulator state
        this.simInterval = null;
        this.simConfig = {
            temp: 38.2,
            hr: 88,
            spo2: 97.5,
            humidity: 55.0,
            aqi: 110,
            bp: 'Normal',
            headache: 'Yes',
            bodyAche: 'Yes',
            fatigue: 'Yes'
        };

        // Telemetry Store & Stats
        this.currentVitals = {
            deviceId: 'ESP32-NODE-DISCONNECTED',
            temperature: 37.0,
            feverSeverity: 'Normal',
            heartRate: 75,
            spo2: 98.0,
            humidity: 50.0,
            aqi: 80,
            bloodPressure: 'Normal',
            headache: 'No',
            bodyAche: 'No',
            fatigue: 'No',
            batteryMv: 4000,
            rssi: -60,
            timestamp: Date.now()
        };

        this.stats = {
            packetsReceived: 0,
            startTime: 0,
            lastPacketTime: 0,
            packetsPerSec: 0
        };

        // Event callbacks
        this.listeners = {
            telemetry: [],
            status: [],
            log: []
        };

        // ECG Canvas Visualizer state
        this.ecgCanvas = null;
        this.ecgCtx = null;
        this.ecgAnimationId = null;
        this.ecgBuffer = [];
        this.ecgPhase = 0;

        // Auto sync options
        this.autoFillEnabled = true;
        this.autoPredictEnabled = false;
        this.lastAutoPredictTime = 0;

        // Initialize BLE UUIDs
        this.BLE_CONFIG = {
            serviceUuid: '4fafc201-1fb5-459e-8fcc-c5c9c331914b',
            telemetryUuid: 'beb5483e-36e1-4688-b7f5-ea07361b26a8',
            commandUuid: 'beb5483e-36e1-4688-b7f5-ea07361b26a9',
            nusServiceUuid: '6e400001-b5a3-f393-e0a9-e50e24dcca9e',
            nusTxUuid: '6e400003-b5a3-f393-e0a9-e50e24dcca9e',
            nusRxUuid: '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
        };
    }

    /* ----------------------------------------------------------------------
       Subscription & Logging Methods
       ---------------------------------------------------------------------- */
    on(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event].push(callback);
        }
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(cb => {
                try { cb(data); } catch(err) { console.error(`[ESP32Hub] Listener Error in ${event}:`, err); }
            });
        }
    }

    log(message, type = 'info') {
        const timeStr = new Date().toLocaleTimeString();
        const logEntry = { time: timeStr, message, type };
        this.emit('log', logEntry);
    }

    setStatus(status, mode = this.activeMode) {
        this.connectionStatus = status;
        this.activeMode = mode;
        this.emit('status', { status, mode, deviceId: this.currentVitals.deviceId });
    }

    /* ----------------------------------------------------------------------
       1. WEB BLUETOOTH (BLE) CONNECTOR
       ---------------------------------------------------------------------- */
    async connectBLE() {
        if (!navigator.bluetooth) {
            this.log('Web Bluetooth is not supported in this browser. Use Chrome, Edge, or Opera.', 'error');
            throw new Error('Web Bluetooth API not supported');
        }

        try {
            this.setStatus('connecting', 'ble');
            this.log('Scanning for ESP32 Bluetooth Low Energy devices...', 'info');

            // Request Bluetooth Device
            this.bleDevice = await navigator.bluetooth.requestDevice({
                filters: [
                    { namePrefix: 'Relivio' },
                    { namePrefix: 'ESP32' }
                ],
                optionalServices: [
                    this.BLE_CONFIG.serviceUuid,
                    this.BLE_CONFIG.nusServiceUuid,
                    'generic_access',
                    0x1809, // Health Thermometer
                    0x180D  // Heart Rate
                ]
            }).catch(async (e) => {
                // Fallback to accepting all devices if prefix filter doesn't match
                this.log('Showing all discoverable BLE devices...', 'warn');
                return await navigator.bluetooth.requestDevice({
                    acceptAllDevices: true,
                    optionalServices: [
                        this.BLE_CONFIG.serviceUuid,
                        this.BLE_CONFIG.nusServiceUuid,
                        0x1809,
                        0x180D
                    ]
                });
            });

            if (!this.bleDevice) {
                this.setStatus('disconnected', 'none');
                return;
            }

            this.log(`Selected Device: ${this.bleDevice.name || 'Unnamed BLE Device'} (${this.bleDevice.id})`, 'success');
            
            // Listen for disconnection
            this.bleDevice.addEventListener('gattserverdisconnected', () => {
                this.log('ESP32 BLE GATT Server Disconnected.', 'warn');
                this.setStatus('disconnected', 'none');
            });

            // Connect GATT Server
            this.log('Connecting to GATT Server...', 'info');
            this.bleServer = await this.bleDevice.gatt.connect();

            // Discover Services
            let service = null;
            try {
                service = await this.bleServer.getPrimaryService(this.BLE_CONFIG.serviceUuid);
                this.log('Found Relivio Custom Vitals Service!', 'success');
            } catch (e) {
                this.log('Relivio service not found, trying Nordic UART Service...', 'warn');
                service = await this.bleServer.getPrimaryService(this.BLE_CONFIG.nusServiceUuid);
            }

            // Get Telemetry Characteristic & start notifications
            try {
                this.bleTelemetryChar = await service.getCharacteristic(this.BLE_CONFIG.telemetryUuid);
            } catch (e) {
                this.bleTelemetryChar = await service.getCharacteristic(this.BLE_CONFIG.nusTxUuid);
            }

            await this.bleTelemetryChar.startNotifications();
            this.bleTelemetryChar.addEventListener('characteristicvaluechanged', (event) => {
                this.handleIncomingRawBLEData(event.target.value);
            });

            // Get Command Characteristic
            try {
                this.bleCommandChar = await service.getCharacteristic(this.BLE_CONFIG.commandUuid);
            } catch(e) {
                try {
                    this.bleCommandChar = await service.getCharacteristic(this.BLE_CONFIG.nusRxUuid);
                } catch(err) {}
            }

            this.currentVitals.deviceId = this.bleDevice.name || 'ESP32-BLE-NODE';
            this.stats.startTime = Date.now();
            this.setStatus('connected', 'ble');
            this.log('BLE Connected! Receiving real-time vital telemetry.', 'success');

        } catch (error) {
            this.log(`BLE Connection Failed: ${error.message}`, 'error');
            this.setStatus('error', 'ble');
            throw error;
        }
    }

    handleIncomingRawBLEData(dataView) {
        try {
            const decoder = new TextDecoder('utf-8');
            const rawString = decoder.decode(dataView);
            this.processIncomingPayload(rawString, 'BLE');
        } catch (err) {
            console.error('[ESP32Hub] BLE decode error:', err);
        }
    }

    async disconnectBLE() {
        if (this.bleDevice && this.bleDevice.gatt.connected) {
            this.bleDevice.gatt.disconnect();
        }
        this.bleDevice = null;
        this.bleServer = null;
        this.bleTelemetryChar = null;
        this.bleCommandChar = null;
        this.setStatus('disconnected', 'none');
        this.log('BLE connection closed.', 'info');
    }

    /* ----------------------------------------------------------------------
       2. USB SERIAL (UART) CONNECTOR (Web Serial & Backend PySerial Hub)
       ---------------------------------------------------------------------- */
    async fetchSerialPorts() {
        try {
            const resp = await fetch('/api/serial/ports');
            const data = await resp.json();
            if (data.success) {
                return data.ports || [];
            }
            return [];
        } catch (err) {
            console.error('[ESP32Hub] Error fetching serial ports:', err);
            return [];
        }
    }

    async connectBackendSerial(port, baudRate = 115200, board = 'ESP32') {
        try {
            this.setStatus('connecting', 'serial');
            this.log(`Opening Server PySerial port ${port} at ${baudRate} baud (${board})...`, 'info');

            const resp = await fetch('/api/serial/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ port, baud_rate: parseInt(baudRate), board })
            });
            const res = await resp.json();

            if (res.success) {
                this.backendSerialConnected = true;
                this.currentVitals.deviceId = `${board}-${port}`;
                this.stats.startTime = Date.now();
                this.setStatus('connected', 'serial');
                this.log(`Server connected to ${port} (${board})! Listening for incoming vitals stream...`, 'success');

                // Connect to WiFi/Server SSE stream if not already active to receive the forwarded serial vitals
                if (!this.eventSource) {
                    this.connectWiFiSSE();
                }
                return true;
            } else {
                throw new Error(res.error || 'Failed to connect backend serial port');
            }
        } catch (err) {
            this.log(`Backend Serial Connection Failed: ${err.message}`, 'error');
            this.setStatus('error', 'serial');
            throw err;
        }
    }

    async disconnectBackendSerial() {
        try {
            const resp = await fetch('/api/serial/disconnect', { method: 'POST' });
            const res = await resp.json();
            this.backendSerialConnected = false;
            this.setStatus('disconnected', 'none');
            this.log(`Backend serial port disconnected.`, 'info');
            return res.success;
        } catch (err) {
            this.log(`Error disconnecting backend serial: ${err.message}`, 'error');
            return false;
        }
    }

    async getBackendSerialStatus() {
        try {
            const resp = await fetch('/api/serial/status');
            const data = await resp.json();
            return data.status || {};
        } catch (err) {
            return { connected: false };
        }
    }

    async connectSerial(baudRate = 115200, board = 'ESP32') {
        if (!navigator.serial) {
            this.log('Web Serial API is not supported in this browser. Falling back to Server Python Serial...', 'warn');
            throw new Error('Web Serial API not supported in this browser. Please use the "Connect via Server (PySerial)" option below.');
        }

        try {
            this.setStatus('connecting', 'serial');
            this.log(`Select your ${board} USB COM Port in the browser dialog...`, 'info');

            this.serialPort = await navigator.serial.requestPort();
            await this.serialPort.open({ baudRate: parseInt(baudRate) });

            this.serialKeepReading = true;
            this.currentVitals.deviceId = `${board}-USB-SERIAL`;
            this.stats.startTime = Date.now();
            this.setStatus('connected', 'serial');
            this.log(`Web Serial Port opened at ${baudRate} baud! Streaming ${board} vitals...`, 'success');

            this.readSerialStream();
        } catch (error) {
            this.log(`Serial Connection Failed: ${error.message}`, 'error');
            this.setStatus('error', 'serial');
            throw error;
        }
    }

    async readSerialStream() {
        const textDecoder = new TextDecoderStream();
        const readableStreamClosed = this.serialPort.readable.pipeTo(textDecoder.writable);
        const reader = textDecoder.readable.getReader();
        this.serialReader = reader;

        let lineBuffer = '';

        try {
            while (this.serialKeepReading) {
                const { value, done } = await reader.read();
                if (done) break;
                if (value) {
                    lineBuffer += value;
                    const lines = lineBuffer.split('\n');
                    lineBuffer = lines.pop(); // Keep incomplete tail

                    for (const line of lines) {
                        const trimmed = line.trim();
                        if (trimmed.length > 0) {
                            this.processIncomingPayload(trimmed, 'Web-Serial');
                        }
                    }
                }
            }
        } catch (err) {
            if (this.serialKeepReading) {
                this.log(`Serial Read Error: ${err.message}`, 'error');
            }
        } finally {
            reader.releaseLock();
        }
    }

    async disconnectSerial() {
        this.serialKeepReading = false;
        if (this.serialReader) {
            try { await this.serialReader.cancel(); } catch (e) {}
        }
        if (this.serialPort) {
            try { await this.serialPort.close(); } catch (e) {}
        }
        this.serialPort = null;
        this.serialReader = null;

        if (this.backendSerialConnected) {
            await this.disconnectBackendSerial();
        }

        this.setStatus('disconnected', 'none');
        this.log('Serial connection closed.', 'info');
    }

    /* ----------------------------------------------------------------------
       3. WIFI CONNECTOR (Flask Backend SSE Stream + Direct REST Polling)
       ---------------------------------------------------------------------- */
    connectWiFiSSE() {
        this.setStatus('connecting', 'wifi');
        this.log('Subscribing to Relivio Real-time IoT Hub SSE Stream (/api/esp32/stream)...', 'info');

        if (this.eventSource) {
            this.eventSource.close();
        }

        this.eventSource = new EventSource('/api/esp32/stream');

        this.eventSource.onopen = () => {
            this.setStatus('connected', 'wifi');
            this.stats.startTime = Date.now();
            this.log('Connected to Relivio WiFi IoT Hub! Ready to receive live ESP32 packets.', 'success');
        };

        this.eventSource.addEventListener('telemetry', (event) => {
            try {
                const data = JSON.parse(event.data);
                this.processNormalizedData(data, 'WiFi-SSE');
            } catch (err) {
                console.error('[ESP32Hub] SSE Parse Error:', err);
            }
        });

        this.eventSource.onerror = (err) => {
            this.log('WiFi SSE Connection interrupted. Auto-reconnecting...', 'warn');
        };
    }

    startWiFiDirectPolling(esp32Ip, intervalMs = 1500) {
        this.wifiTargetIp = esp32Ip.replace('http://', '').replace('/', '');
        this.setStatus('connecting', 'wifi');
        this.log(`Starting direct poll on http://${this.wifiTargetIp}/vitals...`, 'info');

        if (this.wifiPollInterval) clearInterval(this.wifiPollInterval);

        const pollFunc = async () => {
            const targetUrl = `http://${this.wifiTargetIp}/vitals`;
            const proxyUrl = `/api/esp32/proxy?target=${encodeURIComponent(targetUrl)}`;

            try {
                // Try direct fetch first
                let res = await fetch(targetUrl, { signal: AbortSignal.timeout(1200) })
                    .catch(() => fetch(proxyUrl, { signal: AbortSignal.timeout(2000) })); // Fallback to proxy
                
                if (res.ok) {
                    const json = await res.json();
                    const payload = json.data ? json.data : json;
                    this.processNormalizedData(payload, 'WiFi-REST');
                    if (this.connectionStatus !== 'connected') {
                        this.setStatus('connected', 'wifi');
                        this.log(`Direct WiFi link established with ESP32 at ${this.wifiTargetIp}`, 'success');
                    }
                }
            } catch (err) {
                if (this.connectionStatus === 'connected') {
                    this.log(`WiFi poll timeout for ${this.wifiTargetIp}`, 'warn');
                }
            }
        };

        pollFunc();
        this.wifiPollInterval = setInterval(pollFunc, intervalMs);
    }

    disconnectWiFi() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.wifiPollInterval) {
            clearInterval(this.wifiPollInterval);
            this.wifiPollInterval = null;
        }
        this.setStatus('disconnected', 'none');
        this.log('WiFi Hub listener disconnected.', 'info');
    }

    /* ----------------------------------------------------------------------
       4. HARDWARE VIRTUAL SIMULATOR
       ---------------------------------------------------------------------- */
    startSimulator(tickIntervalMs = 1000) {
        this.stopAll();
        this.setStatus('connected', 'simulator');
        this.currentVitals.deviceId = 'ESP32-VIRTUAL-SIMULATOR';
        this.stats.startTime = Date.now();
        this.log('Interactive ESP32 Virtual Simulator activated.', 'success');

        let tick = 0;
        this.simInterval = setInterval(() => {
            tick++;
            
            // Add subtle biological fluctuations
            const tempFluctuation = (Math.sin(tick * 0.2) * 0.08) + ((Math.random() - 0.5) * 0.04);
            const hrFluctuation = Math.round((Math.sin(tick * 0.3) * 2) + ((Math.random() - 0.5) * 2));
            const spo2Fluctuation = (Math.sin(tick * 0.1) * 0.2);

            const simData = {
                device_id: 'ESP32-VIRTUAL-NODE',
                temperature: parseFloat((this.simConfig.temp + tempFluctuation).toFixed(1)),
                heart_rate: Math.max(45, Math.min(180, this.simConfig.hr + hrFluctuation)),
                spo2: parseFloat((Math.min(100, Math.max(90, this.simConfig.spo2 + spo2Fluctuation))).toFixed(1)),
                humidity: parseFloat((this.simConfig.humidity + ((Math.random() - 0.5) * 0.5)).toFixed(1)),
                aqi: this.simConfig.aqi,
                blood_pressure: this.simConfig.bp,
                headache: this.simConfig.headache,
                body_ache: this.simConfig.bodyAche,
                fatigue: this.simConfig.fatigue,
                battery_mv: 4050 + Math.round(Math.sin(tick * 0.05) * 50),
                rssi: -54 + Math.round(Math.sin(tick * 0.1) * 4)
            };

            this.processNormalizedData(simData, 'Simulator');
        }, tickIntervalMs);
    }

    stopSimulator() {
        if (this.simInterval) {
            clearInterval(this.simInterval);
            this.simInterval = null;
        }
        if (this.activeMode === 'simulator') {
            this.setStatus('disconnected', 'none');
            this.log('Virtual Simulator stopped.', 'info');
        }
    }

    /* ----------------------------------------------------------------------
       5. UNIVERSAL DATA PARSER & DISPATCHER
       ---------------------------------------------------------------------- */
    processIncomingPayload(raw, source) {
        if (!raw || typeof raw !== 'string') return;
        
        let cleaned = raw.trim();
        if (cleaned.startsWith('[TX]')) cleaned = cleaned.replace('[TX]', '').trim();

        // 1. Try parsing JSON
        if (cleaned.startsWith('{') && cleaned.endsWith('}')) {
            try {
                const parsed = JSON.parse(cleaned);
                this.processNormalizedData(parsed, source);
                return;
            } catch (err) {}
        }

        // 2. Try parsing Key-Value (e.g. TEMP:38.2,HR:86,SPO2:98)
        if (cleaned.includes(':')) {
            try {
                const pairs = cleaned.split(/[,;\n]/);
                const obj = {};
                for (const pair of pairs) {
                    const [k, v] = pair.split(':').map(s => s.trim());
                    if (k && v) {
                        const lk = k.toLowerCase();
                        if (lk.includes('temp')) obj.temperature = parseFloat(v);
                        else if (lk.includes('hr') || lk.includes('heart')) obj.heart_rate = parseInt(v);
                        else if (lk.includes('spo2') || lk.includes('ox')) obj.spo2 = parseFloat(v);
                        else if (lk.includes('hum')) obj.humidity = parseFloat(v);
                        else if (lk.includes('aqi')) obj.aqi = parseInt(v);
                        else if (lk.includes('bp')) obj.blood_pressure = v;
                    }
                }
                if (Object.keys(obj).length > 0) {
                    this.processNormalizedData(obj, source);
                    return;
                }
            } catch (err) {}
        }

        // Log raw string if not parsed
        this.log(`[${source} Raw]: ${cleaned}`, 'debug');
    }

    processNormalizedData(data, source) {
        this.stats.packetsReceived++;
        this.stats.lastPacketTime = Date.now();

        const temp = parseFloat(data.temperature || data.temp || this.currentVitals.temperature);
        const hr = parseInt(data.heart_rate || data.hr || this.currentVitals.heartRate);
        const spo2 = parseFloat(data.spo2 || this.currentVitals.spo2);
        const humidity = parseFloat(data.humidity || data.hum || this.currentVitals.humidity);
        const aqi = parseInt(data.aqi || this.currentVitals.aqi);
        const bp = data.blood_pressure || data.bp || this.currentVitals.bloodPressure;
        
        let feverSev = data.fever_severity;
        if (!feverSev) {
            if (temp < 37.3) feverSev = 'Normal';
            else if (temp <= 38.0) feverSev = 'Mild Fever';
            else feverSev = 'High Fever';
        }

        const symptoms = data.symptoms || {};
        const headache = data.headache || symptoms.headache || this.currentVitals.headache;
        const bodyAche = data.body_ache || data.bodyAche || symptoms.body_ache || this.currentVitals.bodyAche;
        const fatigue = data.fatigue || symptoms.fatigue || this.currentVitals.fatigue;

        this.currentVitals = {
            deviceId: data.device_id || this.currentVitals.deviceId,
            temperature: temp,
            feverSeverity: feverSev,
            heartRate: hr,
            spo2: spo2,
            humidity: humidity,
            aqi: aqi,
            bloodPressure: bp,
            headache: headache,
            bodyAche: bodyAche,
            fatigue: fatigue,
            batteryMv: data.battery_mv || this.currentVitals.batteryMv,
            rssi: data.rssi || this.currentVitals.rssi,
            packetCount: this.stats.packetsReceived,
            timestamp: Date.now(),
            source: source
        };

        // Emit telemetry event to UI listeners
        this.emit('telemetry', this.currentVitals);

        // Auto Sync with AI Form
        if (this.autoFillEnabled) {
            this.syncVitalsToForm(this.currentVitals);
        }

        // Auto Predict with AI Recommendation
        if (this.autoPredictEnabled) {
            const now = Date.now();
            if (now - this.lastAutoPredictTime > 3000) { // Debounce 3s
                this.lastAutoPredictTime = now;
                const formEl = document.getElementById('predictionForm');
                if (formEl && typeof formEl.requestSubmit === 'function') {
                    formEl.requestSubmit();
                }
            }
        }
    }

    syncVitalsToForm(vitals) {
        // Temperature sync
        const tempInput = document.getElementById('temperature');
        const tempSlider = document.getElementById('tempSlider');
        if (tempInput && tempSlider) {
            tempInput.value = vitals.temperature.toFixed(1);
            tempSlider.value = vitals.temperature.toFixed(1);
            tempInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Heart Rate sync
        const hrInput = document.getElementById('heartRate');
        if (hrInput) {
            hrInput.value = vitals.heartRate;
            hrInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Humidity & AQI sliders
        const humiditySlider = document.getElementById('humidity');
        if (humiditySlider) {
            humiditySlider.value = Math.round(vitals.humidity);
            humiditySlider.dispatchEvent(new Event('input', { bubbles: true }));
        }

        const aqiSlider = document.getElementById('aqi');
        if (aqiSlider) {
            aqiSlider.value = vitals.aqi;
            aqiSlider.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Blood Pressure radio
        if (vitals.bloodPressure) {
            const bpRadio = document.querySelector(`input[name="Blood_Pressure"][value="${vitals.bloodPressure}"]`);
            if (bpRadio) bpRadio.checked = true;
        }

        // Symptom switches
        const setSwitch = (switchId, hiddenId, val) => {
            const cb = document.getElementById(switchId);
            const hid = document.getElementById(hiddenId);
            if (cb && hid) {
                const isYes = (val === 'Yes' || val === true || val === 1);
                cb.checked = isYes;
                hid.value = isYes ? 'Yes' : 'No';
            }
        };

        setSwitch('headacheSwitch', 'headache', vitals.headache);
        setSwitch('bodyAcheSwitch', 'bodyAche', vitals.bodyAche);
        setSwitch('fatigueSwitch', 'fatigue', vitals.fatigue);
    }

    /* ----------------------------------------------------------------------
       6. COMMAND DISPATCH (Send back to ESP32 / Arduino Uno)
       ---------------------------------------------------------------------- */
    async sendCommand(commandStr) {
        const cmd = commandStr.trim().toUpperCase();
        this.log(`Sending command: [${cmd}] via ${this.activeMode}...`, 'info');

        try {
            if (this.activeMode === 'ble' && this.bleCommandChar) {
                const encoder = new TextEncoder();
                await this.bleCommandChar.writeValue(encoder.encode(cmd + '\n'));
                this.log(`BLE Command sent: ${cmd}`, 'success');
            } else if (this.activeMode === 'serial' && this.serialPort && this.serialPort.writable) {
                const encoder = new TextEncoderStream();
                const writableStreamClosed = encoder.readable.pipeTo(this.serialPort.writable);
                const writer = encoder.writable.getWriter();
                await writer.write(cmd + '\n');
                writer.releaseLock();
                this.log(`Web Serial Command sent: ${cmd}`, 'success');
            } else if (this.backendSerialConnected || this.activeMode === 'serial') {
                const resp = await fetch('/api/serial/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const res = await resp.json();
                if (res.success) {
                    this.log(`Server PySerial Command sent: ${cmd}`, 'success');
                } else {
                    this.log(`Server Serial Command failed: ${res.error}`, 'error');
                }
            } else {
                // Post command to Flask endpoint which queues for WiFi devices
                const resp = await fetch('/api/esp32/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd, device_id: this.currentVitals.deviceId })
                });
                const res = await resp.json();
                if (res.success) {
                    this.log(`Server Queued Command: ${cmd}`, 'success');
                }
            }
        } catch (err) {
            this.log(`Command failed: ${err.message}`, 'error');
        }
    }

    /* ----------------------------------------------------------------------
       7. DYNAMIC ECG CANVAS WAVEFORM VISUALIZER
       ---------------------------------------------------------------------- */
    initEcgCanvas(canvasId) {
        this.ecgCanvas = document.getElementById(canvasId);
        if (!this.ecgCanvas) return;

        this.ecgCtx = this.ecgCanvas.getContext('2d');
        this.resizeEcgCanvas();
        window.addEventListener('resize', () => this.resizeEcgCanvas());

        // Initialize wave buffer with mid-line values
        const len = this.ecgCanvas.width || 400;
        this.ecgBuffer = new Array(len).fill(0);
        this.ecgPhase = 0;

        if (this.ecgAnimationId) cancelAnimationFrame(this.ecgAnimationId);
        this.renderEcgFrame();
    }

    resizeEcgCanvas() {
        if (!this.ecgCanvas) return;
        const rect = this.ecgCanvas.parentElement.getBoundingClientRect();
        this.ecgCanvas.width = rect.width;
        this.ecgCanvas.height = 100;
    }

    renderEcgFrame() {
        if (!this.ecgCanvas || !this.ecgCtx) return;

        const ctx = this.ecgCtx;
        const w = this.ecgCanvas.width;
        const h = this.ecgCanvas.height;
        const midY = h / 2;

        // Compute current cardiac cycle speed based on Heart Rate
        const hr = (this.connectionStatus === 'connected') ? this.currentVitals.heartRate : 72;
        const beatsPerSec = hr / 60.0;
        const phaseIncrement = (beatsPerSec * Math.PI * 2) / 60.0; // 60fps

        this.ecgPhase = (this.ecgPhase + phaseIncrement) % (Math.PI * 2);

        // Generate synthetic ECG P-Q-R-S-T curve value
        let sample = 0;
        const p = this.ecgPhase;
        
        // P Wave (Atrial depolarization)
        if (p > 0.4 && p < 0.8) {
            sample = Math.sin((p - 0.4) / 0.4 * Math.PI) * 0.18;
        }
        // Q Wave
        else if (p >= 1.0 && p < 1.1) {
            sample = -0.15;
        }
        // R Wave (Ventricular depolarization spike)
        else if (p >= 1.1 && p < 1.25) {
            sample = Math.sin((p - 1.1) / 0.15 * Math.PI) * 1.0;
        }
        // S Wave
        else if (p >= 1.25 && p < 1.4) {
            sample = -0.32;
        }
        // T Wave (Ventricular repolarization)
        else if (p > 1.8 && p < 2.5) {
            sample = Math.sin((p - 1.8) / 0.7 * Math.PI) * 0.28;
        }

        // Add minor baseline biological noise if connected
        if (this.connectionStatus === 'connected') {
            sample += (Math.random() - 0.5) * 0.03;
        }

        this.ecgBuffer.shift();
        this.ecgBuffer.push(sample);

        // Clear canvas with subtle fading phosphor trail
        ctx.fillStyle = document.body.classList.contains('dark-theme') ? 'rgba(11, 17, 32, 0.95)' : 'rgba(248, 250, 252, 0.95)';
        ctx.fillRect(0, 0, w, h);

        // Draw Medical Grid Lines
        ctx.strokeStyle = document.body.classList.contains('dark-theme') ? 'rgba(56, 189, 248, 0.08)' : 'rgba(2, 132, 199, 0.08)';
        ctx.lineWidth = 1;
        const gridSize = 20;
        ctx.beginPath();
        for (let x = 0; x < w; x += gridSize) {
            ctx.moveTo(x, 0); ctx.lineTo(x, h);
        }
        for (let y = 0; y < h; y += gridSize) {
            ctx.moveTo(0, y); ctx.lineTo(w, y);
        }
        ctx.stroke();

        // Draw ECG Waveform
        const isOnline = (this.connectionStatus === 'connected');
        const waveColor = isOnline ? '#10b981' : '#64748b'; // Emerald when online, muted slate when standby
        
        ctx.strokeStyle = waveColor;
        ctx.lineWidth = 2.2;
        ctx.shadowColor = isOnline ? '#10b981' : 'transparent';
        ctx.shadowBlur = isOnline ? 10 : 0;
        ctx.beginPath();

        const step = w / (this.ecgBuffer.length - 1);
        for (let i = 0; i < this.ecgBuffer.length; i++) {
            const x = i * step;
            const y = midY - (this.ecgBuffer[i] * (h * 0.42));
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0; // Reset shadow

        // Draw pulse sweep head glow dot
        const headX = w - 2;
        const headY = midY - (this.ecgBuffer[this.ecgBuffer.length - 1] * (h * 0.42));
        ctx.fillStyle = isOnline ? '#34d399' : '#94a3b8';
        ctx.beginPath();
        ctx.arc(headX, headY, 4, 0, Math.PI * 2);
        ctx.fill();

        this.ecgAnimationId = requestAnimationFrame(() => this.renderEcgFrame());
    }

    /* ----------------------------------------------------------------------
       8. GENERAL DISCONNECT & RESET
       ---------------------------------------------------------------------- */
    stopAll() {
        if (this.activeMode === 'ble') this.disconnectBLE();
        else if (this.activeMode === 'serial') this.disconnectSerial();
        else if (this.activeMode === 'wifi') this.disconnectWiFi();
        else if (this.activeMode === 'simulator') this.stopSimulator();
        this.setStatus('disconnected', 'none');
    }
}

// Instantiate global singleton
window.esp32Hub = new RelivioESP32Hub();
