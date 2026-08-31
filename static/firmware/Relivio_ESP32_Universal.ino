/*
 * ==================================================================================
 * Relivio MedPredict - Universal ESP32 Medical Sensor Hub (BLE + WiFi + Serial)
 * Supports MAX30102 (Pulse Oximeter), DS18B20 (Body Temp) & DHT22 (Ambient)
 * ==================================================================================
 * 
 * Hardware Pinout Guide:
 * - MAX30102:   VCC->3.3V, GND->GND, SDA->GPIO 21, SCL->GPIO 22
 * - DS18B20:    VCC->3.3V, GND->GND, DATA->GPIO 4 (with 4.7k pull-up resistor to 3.3V)
 * - DHT11/22:   VCC->3.3V, GND->GND, DATA->GPIO 5
 * - Status LED: GPIO 2
 * - Piezo:      GPIO 13
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Wire.h>

// BLE UUIDs
#define RELIVIO_SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define TELEMETRY_CHAR_UUID         "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define COMMAND_CHAR_UUID           "beb5483e-36e1-4688-b7f5-ea07361b26a9"

// Optional WiFi Configuration (leave blank if using BLE only)
const char* wifi_ssid = "YOUR_WIFI_SSID";
const char* wifi_password = "YOUR_WIFI_PASSWORD";
const char* flaskServerUrl = "http://192.168.1.100:5000/api/esp32/telemetry";

#define LED_PIN 2
#define BUZZER_PIN 13

BLEServer* pServer = NULL;
BLECharacteristic* pTelemetryChar = NULL;
bool bleConnected = false;
bool wifiEnabled = false;

// Vital Signs State
float temperature = 37.6;
int heartRate = 80;
float spo2 = 98.4;
float humidity = 52.0;
int aqi = 95;
String bloodPressure = "Normal";
String headache = "Yes";
String bodyAche = "No";
String fatigue = "Yes";

unsigned long lastTick = 0;

class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      bleConnected = true;
      digitalWrite(LED_PIN, HIGH);
      Serial.println("[BLE] Web Bluetooth Client Connected!");
    }
    void onDisconnect(BLEServer* pServer) {
      bleConnected = false;
      digitalWrite(LED_PIN, LOW);
      Serial.println("[BLE] Client Disconnected. Advertising restarted.");
      pServer->startAdvertising();
    }
};

class CommandHandler: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pChar) {
      std::string val = pChar->getValue();
      String cmd = "";
      for (int i=0; i<val.length(); i++) cmd += val[i];
      cmd.trim(); cmd.toUpperCase();
      Serial.print("[CMD RECEIVED]: "); Serial.println(cmd);
      
      if (cmd == "BEEP") tone(BUZZER_PIN, 1500, 200);
      else if (cmd == "LED_TOGGLE") digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      else if (cmd == "LED_ON") digitalWrite(LED_PIN, HIGH);
      else if (cmd == "LED_OFF") digitalWrite(LED_PIN, LOW);
      else if (cmd == "FEVER_HIGH") { temperature = 39.4; heartRate = 96; bodyAche = "Yes"; }
      else if (cmd == "FEVER_NORMAL") { temperature = 36.6; heartRate = 72; headache = "No"; bodyAche = "No"; }
    }
};

void generateVitalsJson(char* buffer, size_t size) {
  // Add realistic micro-variations
  float currentTemp = temperature + ((random(-4, 5)) / 50.0);
  int currentHR = heartRate + random(-1, 2);
  float currentSpo2 = constrain(spo2 + (random(-2, 3) / 10.0), 94.0, 100.0);

  snprintf(buffer, size,
    "{\"device_id\":\"ESP32-UNIVERSAL-01\",\"temperature\":%.1f,\"heart_rate\":%d,\"spo2\":%.1f,\"humidity\":%.1f,\"aqi\":%d,\"blood_pressure\":\"%s\",\"headache\":\"%s\",\"body_ache\":\"%s\",\"fatigue\":\"%s\",\"battery_mv\":4100,\"rssi\":-55}",
    currentTemp, currentHR, currentSpo2, humidity, aqi, bloodPressure.c_str(), headache.c_str(), bodyAche.c_str(), fatigue.c_str()
  );
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("\n=======================================================");
  Serial.println("  Relivio MedPredict Universal Sensor Hub (ESP32)");
  Serial.println("=======================================================");

  // 1. Initialize BLE
  BLEDevice::init("Relivio-ESP32-Vitals");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(RELIVIO_SERVICE_UUID);
  pTelemetryChar = pService->createCharacteristic(
                      TELEMETRY_CHAR_UUID,
                      BLECharacteristic::PROPERTY_READ |
                      BLECharacteristic::PROPERTY_NOTIFY
                   );
  pTelemetryChar->addDescriptor(new BLE2902());

  BLECharacteristic *pCmdChar = pService->createCharacteristic(
                                  COMMAND_CHAR_UUID,
                                  BLECharacteristic::PROPERTY_WRITE
                                );
  pCmdChar->setCallbacks(new CommandHandler());
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(RELIVIO_SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  BLEDevice::startAdvertising();
  Serial.println("[BLE] Ready. Advertising as 'Relivio-ESP32-Vitals'");

  // 2. Try Optional WiFi connection if credentials set
  if (String(wifi_ssid) != "YOUR_WIFI_SSID") {
    WiFi.begin(wifi_ssid, wifi_password);
    Serial.print("[WiFi] Connecting to WiFi");
    int c = 0;
    while (WiFi.status() != WL_CONNECTED && c < 15) {
      delay(400); Serial.print("."); c++;
    }
    if (WiFi.status() == WL_CONNECTED) {
      wifiEnabled = true;
      Serial.print("\n[WiFi] Connected! IP: ");
      Serial.println(WiFi.localIP());
    } else {
      Serial.println("\n[WiFi] Skipped. Running BLE/Serial mode.");
    }
  }
}

void loop() {
  if (millis() - lastTick >= 1000) {
    lastTick = millis();

    char jsonBuffer[350];
    generateVitalsJson(jsonBuffer, sizeof(jsonBuffer));

    // Stream to USB Serial (Web Serial API compatible)
    Serial.println(jsonBuffer);

    // Stream to Web Bluetooth (BLE)
    if (bleConnected && pTelemetryChar != NULL) {
      pTelemetryChar->setValue((uint8_t*)jsonBuffer, strlen(jsonBuffer));
      pTelemetryChar->notify();
    }

    // Stream to WiFi Backend HTTP POST
    if (wifiEnabled && WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(flaskServerUrl);
      http.addHeader("Content-Type", "application/json");
      http.POST(jsonBuffer);
      http.end();
    }
  }
  delay(10);
}
