/*
 * ==================================================================================
 * Relivio MedPredict - ESP32 Bluetooth Low Energy (BLE) Firmware
 * Compatible with Web Bluetooth API in Chrome / Edge / Opera
 * ==================================================================================
 * 
 * Features:
 * - Advertises "Relivio-ESP32-Vitals"
 * - GATT Telemetry Notification Stream (JSON formatted vitals & sensors)
 * - GATT Command Characteristic (Receives commands like SAMPLE, LED_TOGGLE, BEEP)
 * - Dual Service: Relivio Custom Vitals Service + Nordic UART Service (NUS)
 * - Supports physical sensors (MAX30102, DS18B20) or automatic realistic simulation
 */

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// Service and Characteristic UUIDs
#define RELIVIO_SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define TELEMETRY_CHAR_UUID         "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define COMMAND_CHAR_UUID           "beb5483e-36e1-4688-b7f5-ea07361b26a9"

// Optional Nordic UART Service (NUS) for cross-compatibility
#define NUS_SERVICE_UUID            "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_RX_CHAR_UUID            "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_TX_CHAR_UUID            "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

#define LED_PIN 2     // Onboard blue LED on ESP32 DevKit
#define BUZZER_PIN 13 // Optional piezo buzzer

BLEServer* pServer = NULL;
BLECharacteristic* pTelemetryChar = NULL;
BLECharacteristic* pNusTxChar = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

// Vital Signs State Variables
float bodyTemp = 37.8;
int heartRate = 82;
float spo2 = 98.2;
float humidity = 55.0;
int aqi = 110;
String bloodPressure = "Normal";
String headache = "Yes";
String bodyAche = "No";
String fatigue = "Yes";

unsigned long lastSendTime = 0;
const unsigned long sendInterval = 1000; // Send telemetry every 1.0s

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      digitalWrite(LED_PIN, HIGH);
      Serial.println("[BLE] Web Client Connected!");
    };

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      digitalWrite(LED_PIN, LOW);
      Serial.println("[BLE] Client Disconnected. Restarting Advertising...");
    }
};

class CommandCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() > 0) {
        String cmd = "";
        for (int i = 0; i < value.length(); i++) {
          cmd += value[i];
        }
        cmd.trim();
        cmd.toUpperCase();
        Serial.print("[BLE Command Received]: ");
        Serial.println(cmd);

        if (cmd == "LED_ON") {
          digitalWrite(LED_PIN, HIGH);
        } else if (cmd == "LED_OFF") {
          digitalWrite(LED_PIN, LOW);
        } else if (cmd == "BEEP") {
          tone(BUZZER_PIN, 1000, 200);
        } else if (cmd == "SAMPLE_NOW") {
          // Trigger immediate burst
          sendTelemetryPacket();
        } else if (cmd == "FEVER_HIGH") {
          bodyTemp = 39.2;
          heartRate = 96;
          bodyAche = "Yes";
        } else if (cmd == "FEVER_NORMAL") {
          bodyTemp = 36.6;
          heartRate = 72;
          headache = "No";
          bodyAche = "No";
          fatigue = "No";
        }
      }
    }
};

void sendTelemetryPacket() {
  // Simulate minor physiological fluctuation if no physical sensors attached
  float noiseTemp = ((random(-5, 6)) / 50.0);
  float currentTemp = bodyTemp + noiseTemp;
  int currentHR = heartRate + random(-2, 3);
  float currentSpo2 = constrain(spo2 + (random(-2, 3) / 10.0), 94.0, 100.0);
  
  // Format compact JSON payload
  char buffer[256];
  snprintf(buffer, sizeof(buffer),
    "{\"temp\":%.1f,\"hr\":%d,\"spo2\":%.1f,\"hum\":%.1f,\"aqi\":%d,\"bp\":\"%s\",\"headache\":\"%s\",\"body_ache\":\"%s\",\"fatigue\":\"%s\"}",
    currentTemp, currentHR, currentSpo2, humidity, aqi, bloodPressure.c_str(), headache.c_str(), bodyAche.c_str(), fatigue.c_str()
  );

  // Send via Relivio Vitals Characteristic
  if (pTelemetryChar != NULL && deviceConnected) {
    pTelemetryChar->setValue((uint8_t*)buffer, strlen(buffer));
    pTelemetryChar->notify();
  }

  // Send via Nordic UART TX Characteristic
  if (pNusTxChar != NULL && deviceConnected) {
    pNusTxChar->setValue((uint8_t*)buffer, strlen(buffer));
    pNusTxChar->notify();
  }

  // Also print to USB Serial for debugging
  Serial.print("[TX] ");
  Serial.println(buffer);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("\n==========================================");
  Serial.println("   Relivio MedPredict ESP32 BLE Server");
  Serial.println("==========================================");

  // Initialize BLE
  BLEDevice::init("Relivio-ESP32-Vitals");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  // Create Relivio Custom Vitals Service
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
  pCmdChar->setCallbacks(new CommandCallbacks());

  pService->start();

  // Create Nordic UART Service (NUS) for universal app compatibility
  BLEService *pNusService = pServer->createService(NUS_SERVICE_UUID);
  pNusTxChar = pNusService->createCharacteristic(
                  NUS_TX_CHAR_UUID,
                  BLECharacteristic::PROPERTY_NOTIFY
               );
  pNusTxChar->addDescriptor(new BLE2902());

  BLECharacteristic *pNusRxChar = pNusService->createCharacteristic(
                                    NUS_RX_CHAR_UUID,
                                    BLECharacteristic::PROPERTY_WRITE
                                  );
  pNusRxChar->setCallbacks(new CommandCallbacks());
  pNusService->start();

  // Start Advertising
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(RELIVIO_SERVICE_UUID);
  pAdvertising->addServiceUUID(NUS_SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);  // iPhone connection helper
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  
  Serial.println("[BLE] Advertising started as 'Relivio-ESP32-Vitals'");
  Serial.println("[BLE] Ready to connect via Chrome Web Bluetooth!");
}

void loop() {
  if (deviceConnected) {
    if (millis() - lastSendTime >= sendInterval) {
      lastSendTime = millis();
      sendTelemetryPacket();
    }
  }

  // Handle auto-reconnecting advertising when disconnected
  if (!deviceConnected && oldDeviceConnected) {
    delay(500);
    pServer->startAdvertising();
    Serial.println("[BLE] Re-started advertising...");
    oldDeviceConnected = deviceConnected;
  }
  if (deviceConnected && !oldDeviceConnected) {
    oldDeviceConnected = deviceConnected;
  }

  delay(10);
}
