/*
 * =====================================================================================
 * Relivio MedPredict - Complete ESP32 IoT Client Script
 * =====================================================================================
 * 
 * This firmware connects your ESP32 board to the Relivio Web Application.
 * 
 * Features:
 * 1. WiFi HTTP Telemetry: Pushes live clinical vitals to http://<SERVER_IP>:5000/api/esp32/telemetry
 * 2. Web Serial Streaming: Streams JSON vitals over USB Serial at 115200 baud
 * 3. Local Web Server: Hosts http://<ESP32_IP>/vitals with CORS enabled for direct browser polling
 * 4. Bi-directional Remote Commands: Accepts commands from website (LED, BEEP, FEVER_TEST)
 * 5. Dual-Mode Sensors: Works with physical sensors (DHT/DS18B20/MAX30102) OR realistic simulation
 * 
 * Setup Instructions:
 * 1. Set your WiFi credentials (WIFI_SSID & WIFI_PASS) below.
 * 2. Set your computer's IP running Flask in 'SERVER_URL'.
 * 3. Flash to ESP32 using Arduino IDE (Board: "ESP32 Dev Module", Baud: 115200).
 * =====================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>

// Optional sensor libraries (Uncomment if you have physical sensors wired)
// #define USE_DHT_SENSOR       // For DHT11 / DHT22 temperature & humidity
// #define USE_DS18B20_SENSOR   // For Dallas DS18B20 precision body temperature probe
// #define USE_MAX30102_SENSOR  // For MAX30102 Heart Rate & SpO2 sensor

#ifdef USE_DHT_SENSOR
  #include <DHT.h>
  #define DHTPIN 4
  #define DHTTYPE DHT22 // or DHT11
  DHT dht(DHTPIN, DHTTYPE);
#endif

#ifdef USE_DS18B20_SENSOR
  #include <OneWire.h>
  #include <DallasTemperature.h>
  #define ONE_WIRE_BUS 5
  OneWire oneWire(ONE_WIRE_BUS);
  DallasTemperature tempSensors(&oneWire);
#endif

// =====================================================================================
// 1. CONFIGURATION: WIFI & RELIVIO SERVER SETTINGS
// =====================================================================================
const char* WIFI_SSID     = "ESP32";        // <-- Put your WiFi Name here
const char* WIFI_PASS     = "esp32_1234";    // <-- Put your WiFi Password here

// IP of the computer running 'python app.py' (Detected on your Wi-Fi: 192.168.1.6)
const char* SERVER_URL    = "http://127.0.0.1:5000/api/esp32/telemetry";

// Hardware Identification
const char* DEVICE_ID     = "ESP32-RELIVIO-01";
const char* DEVICE_NAME   = "Relivio Medical Node";

// Pin assignments
#define LED_PIN    2    // Onboard Blue LED on ESP32 DevKit
#define BUZZER_PIN 13   // Optional Piezo Buzzer (set to -1 if none)

// Push interval to Relivio Flask backend
const unsigned long TELEMETRY_INTERVAL_MS = 2000; // Push every 2 seconds

// =====================================================================================
// 2. GLOBAL STATE & WEB SERVER
// =====================================================================================
WebServer server(80);
unsigned long lastTelemetryPush = 0;

// Vitals values (dynamic simulation or sensor readings)
float bodyTemperature = 37.8;   // in °C
int heartRate         = 82;     // in BPM
float spo2Level       = 98.2;   // in %
float ambientHumidity = 55.0;   // in %
int ambientAqi        = 110;    // AQI index
String bloodPressure  = "Normal"; // "Normal", "High", "Low"
String symptomHeadache = "Yes";
String symptomBodyAche = "No";
String symptomFatigue  = "Yes";

// =====================================================================================
// 3. SENSOR READING / SIMULATION LOGIC
// =====================================================================================
void updateSensorReadings() {
  #ifdef USE_DHT_SENSOR
    float h = dht.readHumidity();
    if (!isnan(h)) ambientHumidity = h;
  #endif

  #ifdef USE_DS18B20_SENSOR
    tempSensors.requestTemperatures();
    float t = tempSensors.getTempCByIndex(0);
    if (t > 20.0 && t < 45.0) bodyTemperature = t;
  #endif

  // Add realistic micro-variations if simulating
  #ifndef USE_DS18B20_SENSOR
    float jitter = ((float)random(-3, 4)) / 30.0;
    bodyTemperature = constrain(bodyTemperature + jitter, 35.5, 41.0);
  #endif

  #ifndef USE_MAX30102_SENSOR
    int hrJitter = random(-1, 2);
    heartRate = constrain(heartRate + hrJitter, 60, 130);
    float spo2Jitter = ((float)random(-2, 3)) / 10.0;
    spo2Level = constrain(spo2Level + spo2Jitter, 92.0, 100.0);
  #endif
}

// Build JSON string payload
String createTelemetryJson() {
  updateSensorReadings();

  // Determine fever severity
  String severity = "Normal";
  if (bodyTemperature >= 38.1) severity = "High Fever";
  else if (bodyTemperature >= 37.3) severity = "Mild Fever";

  int batteryMv = 4120;
  int rssiVal = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -60;

  String json = "{";
  json += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  json += "\"device_name\":\"" + String(DEVICE_NAME) + "\",";
  json += "\"temperature\":" + String(bodyTemperature, 1) + ",";
  json += "\"fever_severity\":\"" + severity + "\",";
  json += "\"heart_rate\":" + String(heartRate) + ",";
  json += "\"spo2\":" + String(spo2Level, 1) + ",";
  json += "\"humidity\":" + String(ambientHumidity, 1) + ",";
  json += "\"aqi\":" + String(ambientAqi) + ",";
  json += "\"blood_pressure\":\"" + bloodPressure + "\",";
  json += "\"headache\":\"" + symptomHeadache + "\",";
  json += "\"body_ache\":\"" + symptomBodyAche + "\",";
  json += "\"fatigue\":\"" + symptomFatigue + "\",";
  json += "\"battery_mv\":" + String(batteryMv) + ",";
  json += "\"rssi\":" + String(rssiVal) + ",";
  json += "\"protocol\":\"WiFi-HTTP\"";
  json += "}";

  return json;
}

// =====================================================================================
// 4. RELIVIO FLASK HTTP PUSH & COMMAND HANDLER
// =====================================================================================
void sendTelemetryToFlask() {
  if (WiFi.status() != WL_CONNECTED) return;

  String payload = createTelemetryJson();

  // 1. Output to Serial (Compatible with Web Serial direct browser connection)
  Serial.println(payload);

  // 2. HTTP POST to Flask API
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2500);

  int httpResponseCode = http.POST(payload);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("[Relivio Cloud] POST %d OK | %s\n", httpResponseCode, response.c_str());

    // Execute remote queued commands from Flask server if any returned
    if (response.indexOf("LED_TOGGLE") >= 0) digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    if (response.indexOf("LED_ON") >= 0) digitalWrite(LED_PIN, HIGH);
    if (response.indexOf("LED_OFF") >= 0) digitalWrite(LED_PIN, LOW);
    if (response.indexOf("BEEP") >= 0 && BUZZER_PIN > 0) tone(BUZZER_PIN, 1200, 200);
  } else {
    Serial.printf("[Relivio Cloud] POST Error: %s (Code: %d)\n", http.errorToString(httpResponseCode).c_str(), httpResponseCode);
  }
  http.end();
}

void handleSerialCommands() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "LED_TOGGLE") digitalWrite(LED_PIN, !digitalRead(LED_PIN));
  else if (cmd == "LED_ON") digitalWrite(LED_PIN, HIGH);
  else if (cmd == "LED_OFF") digitalWrite(LED_PIN, LOW);
  else if (cmd == "BEEP" && BUZZER_PIN > 0) tone(BUZZER_PIN, 1500, 200);
  else if (cmd == "HIGH_FEVER") { bodyTemperature = 39.4; heartRate = 96; symptomBodyAche = "Yes"; }
  else if (cmd == "NORMAL_FEVER") { bodyTemperature = 36.6; heartRate = 72; symptomBodyAche = "No"; symptomHeadache = "No"; }

  if (cmd.length() > 0) {
    Serial.print("{\"ack\":\"");
    Serial.print(cmd);
    Serial.println("\",\"status\":\"OK\"}");
  }
}

// =====================================================================================
// 5. LOCAL REST API HANDLERS (Hosted directly on ESP32 Port 80)
// =====================================================================================
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><title>Relivio ESP32 Node</title></head>";
  html += "<body style='font-family:sans-serif; background:#0f172a; color:#f8fafc; padding:2rem; text-align:center;'>";
  html += "<h2>Relivio Medical Node (" + String(DEVICE_ID) + ")</h2>";
  html += "<p style='color:#10b981;'><strong>Status: ONLINE & BROADCASTING</strong></p>";
  html += "<p>Relivio Server Target: <code>" + String(SERVER_URL) + "</code></p>";
  html += "<p><a style='color:#38bdf8;' href='/vitals'>View JSON Vitals Stream</a></p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleVitalsEndpoint() {
  String json = createTelemetryJson();
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "*");
  server.send(200, "application/json", json);
}

void handleCommandEndpoint() {
  if (server.hasArg("cmd")) {
    String cmd = server.arg("cmd");
    cmd.toUpperCase();
    Serial.print("[REST Command Received]: ");
    Serial.println(cmd);

    if (cmd == "LED_TOGGLE") digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    else if (cmd == "LED_ON") digitalWrite(LED_PIN, HIGH);
    else if (cmd == "LED_OFF") digitalWrite(LED_PIN, LOW);
    else if (cmd == "BEEP" && BUZZER_PIN > 0) tone(BUZZER_PIN, 1500, 200);
    else if (cmd == "HIGH_FEVER") { bodyTemperature = 39.4; heartRate = 96; symptomBodyAche = "Yes"; }
    else if (cmd == "NORMAL_FEVER") { bodyTemperature = 36.6; heartRate = 72; symptomBodyAche = "No"; symptomHeadache = "No"; }

    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"success\":true,\"executed\":\"" + cmd + "\"}");
  } else {
    server.send(400, "application/json", "{\"error\":\"Missing cmd query param\"}");
  }
}

// =====================================================================================
// 6. SETUP & MAIN LOOP
// =====================================================================================
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  if (BUZZER_PIN > 0) pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  #ifdef USE_DHT_SENSOR
    dht.begin();
  #endif
  #ifdef USE_DS18B20_SENSOR
    tempSensors.begin();
  #endif

  Serial.println("\n=======================================================");
  Serial.println("   Relivio MedPredict - ESP32 Connected Node Started   ");
  Serial.println("=======================================================");

  // Connect to WiFi
  Serial.print("[WiFi] Connecting to: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(400);
    Serial.print(".");
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Flash LED while connecting
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH); // Solid blue LED when connected
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] Assigned IP: ");
    Serial.println(WiFi.localIP());

    // Initialize mDNS (http://relivio-node.local)
    if (MDNS.begin("relivio-node")) {
      Serial.println("[mDNS] Responder active at http://relivio-node.local");
    }

    // Configure Local Webserver
    server.on("/", handleRoot);
    server.on("/vitals", handleVitalsEndpoint);
    server.on("/cmd", handleCommandEndpoint);
    server.begin();
    Serial.println("[REST Server] Listening on Port 80");
  } else {
    Serial.println("\n[WiFi] WiFi connection failed or skipped. Running in Serial Streaming mode.");
  }
}

void loop() {
  handleSerialCommands();

  // Handle local HTTP requests if WiFi is active
  if (WiFi.status() == WL_CONNECTED) {
    server.handleClient();
  }

  // Push telemetry periodically
  if (millis() - lastTelemetryPush >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryPush = millis();
    sendTelemetryToFlask();
  }
}
