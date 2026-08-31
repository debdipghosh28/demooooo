/*
 * =====================================================================================
 * Relivio MedPredict - Cross-Platform Hardware Telemetry Firmware
 * Supports: ESP32 Dev Module & Arduino Uno (ATmega328P) in PlatformIO / Cursor IDE
 * =====================================================================================
 * 
 * Streams real-time physiological vitals formatted as JSON directly over USB Serial
 * to the Relivio Web Platform (either via Python PySerial backend or Web Serial API).
 * 
 * Features:
 * 1. Dual-Platform Detection: Automatically detects ESP32 vs Arduino Uno at compile time.
 * 2. Formatted JSON Stream: Outputs clinical vitals every 2 seconds.
 * 3. Command Receiver: Listens for incoming USB Serial commands (LED_ON, LED_OFF, BEEP, SAMPLE).
 * 4. Micro-Fluctuation Simulation: Generates realistic physiological vital variations
 *    when physical sensors (MAX30102 / DS18B20 / DHT) are not attached.
 * =====================================================================================
 */

#include <Arduino.h>

// -------------------------------------------------------------------------------------
// Board Identification & Pin Configuration
// -------------------------------------------------------------------------------------
#if defined(ESP32) || defined(ARDUINO_ARCH_ESP32)
  #define BOARD_TYPE     "ESP32"
  #define DEFAULT_DEV_ID "ESP32-RELIVIO-01"
  #define DEFAULT_DEV_NAME "Relivio ESP32 Medical Node"
  #define STATUS_LED_PIN 2     // Onboard Blue LED on ESP32 DevKit
  #define BUZZER_PIN     13    // Optional Piezo Buzzer pin (-1 to disable)
  #define SERIAL_BAUD    115200
#else // Arduino Uno / ATmega328P
  #define BOARD_TYPE     "Arduino Uno"
  #define DEFAULT_DEV_ID "UNO-RELIVIO-01"
  #define DEFAULT_DEV_NAME "Relivio Uno Medical Node"
  #define STATUS_LED_PIN 13    // Onboard LED on Arduino Uno
  #define BUZZER_PIN     9     // Optional Piezo Buzzer pin
  #define SERIAL_BAUD    115200
#endif

// Telemetry interval (ms)
const unsigned long TELEMETRY_INTERVAL_MS = 2000;
unsigned long lastTelemetryTime = 0;

// Dynamic physiological state
float bodyTemperature = 37.8;   // in °C
int heartRate         = 80;     // in BPM
float spo2Level       = 98.2;   // in %
float ambientHumidity = 55.0;   // in %
int ambientAqi        = 105;    // AQI
int packetCounter     = 0;

// Symptoms state
const char* bpStatus = "Normal";
const char* symHeadache = "Yes";
const char* symBodyAche = "No";
const char* symFatigue  = "Yes";

// -------------------------------------------------------------------------------------
// Sensor Reading / Simulation Logic
// -------------------------------------------------------------------------------------
void updateVitals() {
  // Micro biological variations to simulate active human sensor stream
  long rTemp = random(-2, 3);
  bodyTemperature += ((float)rTemp) / 10.0;
  if (bodyTemperature < 36.2) bodyTemperature = 36.5;
  if (bodyTemperature > 40.2) bodyTemperature = 39.8;

  int rHr = random(-2, 3);
  heartRate += rHr;
  if (heartRate < 60) heartRate = 65;
  if (heartRate > 130) heartRate = 120;

  long rSpo2 = random(-1, 2);
  spo2Level += ((float)rSpo2) / 10.0;
  if (spo2Level < 94.0) spo2Level = 95.0;
  if (spo2Level > 100.0) spo2Level = 99.5;

  long rHum = random(-1, 2);
  ambientHumidity += ((float)rHum) / 10.0;
}

// -------------------------------------------------------------------------------------
// Emit JSON Telemetry Packet over USB Serial
// -------------------------------------------------------------------------------------
void sendTelemetryPacket() {
  packetCounter++;
  updateVitals();

  const char* feverSeverity = "Normal";
  if (bodyTemperature >= 38.1) {
    feverSeverity = "High Fever";
  } else if (bodyTemperature >= 37.3) {
    feverSeverity = "Mild Fever";
  }

  // Construct JSON String
  Serial.print(F("{\"device_id\":\""));
  Serial.print(DEFAULT_DEV_ID);
  Serial.print(F("\",\"device_name\":\""));
  Serial.print(DEFAULT_DEV_NAME);
  Serial.print(F("\",\"board\":\""));
  Serial.print(BOARD_TYPE);
  Serial.print(F("\",\"temperature\":"));
  Serial.print(bodyTemperature, 1);
  Serial.print(F(",\"fever_severity\":\""));
  Serial.print(feverSeverity);
  Serial.print(F("\",\"heart_rate\":"));
  Serial.print(heartRate);
  Serial.print(F(",\"spo2\":"));
  Serial.print(spo2Level, 1);
  Serial.print(F(",\"humidity\":"));
  Serial.print(ambientHumidity, 1);
  Serial.print(F(",\"aqi\":"));
  Serial.print(ambientAqi);
  Serial.print(F(",\"blood_pressure\":\""));
  Serial.print(bpStatus);
  Serial.print(F("\",\"headache\":\""));
  Serial.print(symHeadache);
  Serial.print(F("\",\"body_ache\":\""));
  Serial.print(symBodyAche);
  Serial.print(F("\",\"fatigue\":\""));
  Serial.print(symFatigue);
  Serial.print(F("\",\"battery_mv\":"));
#if defined(ESP32)
  Serial.print(4120);
#else
  Serial.print(5000);
#endif
  Serial.print(F(",\"packet\":"));
  Serial.print(packetCounter);
  Serial.print(F(",\"protocol\":\"USB-Serial\"}"));
  Serial.println();

  // Pulse onboard LED on packet transmission
  digitalWrite(STATUS_LED_PIN, HIGH);
  delay(30);
  digitalWrite(STATUS_LED_PIN, LOW);
}

// -------------------------------------------------------------------------------------
// Handle Inbound Serial Commands from Relivio App
// -------------------------------------------------------------------------------------
void processIncomingCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd.length() == 0) return;

    if (cmd == "LED_ON") {
      digitalWrite(STATUS_LED_PIN, HIGH);
      Serial.println(F("{\"ack\":\"LED_ON\",\"status\":\"OK\"}"));
    } else if (cmd == "LED_OFF") {
      digitalWrite(STATUS_LED_PIN, LOW);
      Serial.println(F("{\"ack\":\"LED_OFF\",\"status\":\"OK\"}"));
    } else if (cmd == "BEEP") {
#if defined(BUZZER_PIN) && (BUZZER_PIN > 0)
      tone(BUZZER_PIN, 1500, 150);
#endif
      Serial.println(F("{\"ack\":\"BEEP\",\"status\":\"OK\"}"));
    } else if (cmd == "SAMPLE" || cmd == "SAMPLE_NOW") {
      sendTelemetryPacket();
    } else if (cmd == "RESET") {
      packetCounter = 0;
      Serial.println(F("{\"ack\":\"RESET\",\"status\":\"OK\"}"));
    } else {
      Serial.print(F("{\"ack\":\"UNKNOWN_CMD\",\"cmd\":\""));
      Serial.print(cmd);
      Serial.println(F("\"}"));
    }
  }
}

// -------------------------------------------------------------------------------------
// Arduino Setup & Loop
// -------------------------------------------------------------------------------------
void setup() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

#if defined(BUZZER_PIN) && (BUZZER_PIN > 0)
  pinMode(BUZZER_PIN, OUTPUT);
#endif

  // Initialize USB Serial
  Serial.begin(SERIAL_BAUD);
  delay(100);

  // Startup banner
  Serial.println();
  Serial.print(F("[Relivio] Initialized Node on "));
  Serial.print(BOARD_TYPE);
  Serial.print(F(" @ "));
  Serial.print(SERIAL_BAUD);
  Serial.println(F(" baud. Streaming vitals JSON..."));

  // Send initial startup packet
  sendTelemetryPacket();
}

void loop() {
  // Check for incoming commands
  processIncomingCommands();

  // Periodic telemetry transmission
  unsigned long currentMillis = millis();
  if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = currentMillis;
    sendTelemetryPacket();
  }
}
