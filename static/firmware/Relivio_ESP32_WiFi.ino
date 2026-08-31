/*
 * ==================================================================================
 * Relivio MedPredict - ESP32 WiFi Telemetry & REST Server Firmware
 * Real-time Clinical Data Bridge to Flask Backend
 * ==================================================================================
 * 
 * Features:
 * - Connects to local WiFi
 * - Pushes telemetry via HTTP POST to http://<YOUR_FLASK_SERVER_IP>:5000/api/esp32/telemetry
 * - Hosts local REST WebServer at http://<ESP32_IP>/vitals with CORS enabled
 * - Receives and executes remote commands from Relivio MedPredict
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <ArduinoJson.h> // Library: ArduinoJson by Benoit Blanchon (or uses snprintf if missing)

// -------------------------------------------------------------
// USER CONFIGURATION (Update with your WiFi & Server Details)
// -------------------------------------------------------------
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// IP Address of the computer running 'python app.py'
// e.g. "http://192.168.1.105:5000/api/esp32/telemetry"
const char* relivioServerEndpoint = "http://192.168.1.100:5000/api/esp32/telemetry";

#define LED_PIN 2     // Onboard status LED
#define BUZZER_PIN 13 // Piezo buzzer

WebServer server(80);

// Vital Signs State Variables
float bodyTemp = 38.2;
int heartRate = 86;
float spo2 = 97.8;
float humidity = 58.0;
int aqi = 115;
String bloodPressure = "Normal";
String headache = "Yes";
String bodyAche = "Yes";
String fatigue = "Yes";

unsigned long lastHttpPush = 0;
const unsigned long httpPushInterval = 2000; // Push every 2 seconds

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><title>Relivio ESP32 Node</title></head>";
  html += "<body style='font-family:sans-serif; background:#0f172a; color:#f8fafc; padding:2rem; text-align:center;'>";
  html += "<h1>Relivio MedPredict ESP32 WiFi Node</h1>";
  html += "<p>Status: <strong style='color:#10b981;'>ONLINE & ACTIVE</strong></p>";
  html += "<p>JSON Telemetry: <a style='color:#38bdf8;' href='/vitals'>/vitals</a></p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleVitalsJson() {
  char buffer[300];
  snprintf(buffer, sizeof(buffer),
    "{\"device_id\":\"ESP32-WIFI-NODE-1\",\"temperature\":%.1f,\"heart_rate\":%d,\"spo2\":%.1f,\"humidity\":%.1f,\"aqi\":%d,\"blood_pressure\":\"%s\",\"headache\":\"%s\",\"body_ache\":\"%s\",\"fatigue\":\"%s\",\"battery_mv\":%d,\"rssi\":%d}",
    bodyTemp, heartRate, spo2, humidity, aqi, bloodPressure.c_str(), headache.c_str(), bodyAche.c_str(), fatigue.c_str(), 4150, (int)WiFi.RSSI()
  );
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Headers", "*");
  server.send(200, "application/json", buffer);
}

void handleCommand() {
  if (server.hasArg("cmd")) {
    String cmd = server.arg("cmd");
    cmd.toUpperCase();
    Serial.print("[WiFi REST Command]: ");
    Serial.println(cmd);
    
    if (cmd == "LED_TOGGLE") digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    else if (cmd == "LED_ON") digitalWrite(LED_PIN, HIGH);
    else if (cmd == "LED_OFF") digitalWrite(LED_PIN, LOW);
    else if (cmd == "BEEP") tone(BUZZER_PIN, 1200, 150);
    else if (cmd == "FEVER_HIGH") { bodyTemp = 39.2; heartRate = 98; }
    else if (cmd == "FEVER_NORMAL") { bodyTemp = 36.6; heartRate = 72; }
    
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"success\":true,\"executed\":\"" + cmd + "\"}");
  } else {
    server.send(400, "application/json", "{\"error\":\"Missing cmd parameter\"}");
  }
}

void pushTelemetryToRelivioServer() {
  if (WiFi.status() != WL_CONNECTED) return;

  // Add realistic small fluctuations
  float currentTemp = bodyTemp + ((random(-4, 5)) / 50.0);
  int currentHR = heartRate + random(-1, 2);
  float currentSpo2 = constrain(spo2 + (random(-2, 3) / 10.0), 94.0, 100.0);

  char payload[350];
  snprintf(payload, sizeof(payload),
    "{\"device_id\":\"ESP32-WIFI-NODE-1\",\"device_name\":\"ESP32 WiFi Node\",\"temperature\":%.1f,\"heart_rate\":%d,\"spo2\":%.1f,\"humidity\":%.1f,\"aqi\":%d,\"blood_pressure\":\"%s\",\"headache\":\"%s\",\"body_ache\":\"%s\",\"fatigue\":\"%s\",\"battery_mv\":4150,\"rssi\":%d,\"protocol\":\"WiFi-HTTP\"}",
    currentTemp, currentHR, currentSpo2, humidity, aqi, bloodPressure.c_str(), headache.c_str(), bodyAche.c_str(), fatigue.c_str(), (int)WiFi.RSSI()
  );

  HTTPClient http;
  http.begin(relivioServerEndpoint);
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST(payload);
  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP POST] Success (Code %d): %s\n", httpCode, response.c_str());
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Flash LED on success
  } else {
    Serial.printf("[HTTP POST] Error: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("\n==========================================");
  Serial.println("   Relivio MedPredict ESP32 WiFi Node");
  Serial.println("==========================================");

  // Connect to WiFi
  Serial.print("[WiFi] Connecting to: ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());

    // Setup mDNS responder
    if (MDNS.begin("esp32-relivio")) {
      Serial.println("[mDNS] Responder started at http://esp32-relivio.local");
    }

    // Configure WebServer routes
    server.on("/", handleRoot);
    server.on("/vitals", handleVitalsJson);
    server.on("/cmd", handleCommand);
    server.begin();
    Serial.println("[HTTP Server] Listening on Port 80");
  } else {
    Serial.println("\n[WiFi] Connection timeout. Running in standalone mode.");
  }
}

void loop() {
  server.handleClient();

  if (millis() - lastHttpPush >= httpPushInterval) {
    lastHttpPush = millis();
    pushTelemetryToRelivioServer();
  }
}
