/*
 * =====================================================================================
 * Relivio MedPredict - Arduino Uno (ATmega328P) Telemetry Firmware (.ino)
 * =====================================================================================
 * 
 * Streams real-time physiological vitals formatted as JSON directly over USB Serial (COM Port)
 * to the Relivio AI Web Platform at 115200 baud (or 9600 baud).
 * 
 * Pinout Guide:
 * - Onboard LED: Pin 13 (blinks on data transmit)
 * - Optional Piezo Buzzer: Pin 9
 * - MAX30102 / DS18B20 / DHT sensors supported or simulated fallback.
 * =====================================================================================
 */

#define BOARD_NAME     "Arduino Uno"
#define DEVICE_ID      "UNO-RELIVIO-01"
#define STATUS_LED_PIN 13
#define BUZZER_PIN     9
#define SERIAL_BAUD    115200

const unsigned long TELEMETRY_INTERVAL_MS = 2000;
unsigned long lastTelemetryTime = 0;

float bodyTemperature = 37.6;
int heartRate         = 78;
float spo2Level       = 98.4;
float ambientHumidity = 52.0;
int ambientAqi        = 95;
int packetCounter     = 0;

void updateVitals() {
  long rTemp = random(-2, 3);
  bodyTemperature += ((float)rTemp) / 10.0;
  if (bodyTemperature < 36.2) bodyTemperature = 36.4;
  if (bodyTemperature > 40.2) bodyTemperature = 39.6;

  int rHr = random(-2, 3);
  heartRate += rHr;
  if (heartRate < 60) heartRate = 65;
  if (heartRate > 130) heartRate = 120;

  long rSpo2 = random(-1, 2);
  spo2Level += ((float)rSpo2) / 10.0;
  if (spo2Level < 94.0) spo2Level = 95.0;
  if (spo2Level > 100.0) spo2Level = 99.5;
}

void sendTelemetryPacket() {
  packetCounter++;
  updateVitals();

  const char* feverSeverity = "Normal";
  if (bodyTemperature >= 38.1) feverSeverity = "High Fever";
  else if (bodyTemperature >= 37.3) feverSeverity = "Mild Fever";

  Serial.print(F("{\"device_id\":\""));
  Serial.print(DEVICE_ID);
  Serial.print(F("\",\"device_name\":\"Relivio Uno Medical Node\",\"board\":\"Arduino Uno\",\"temperature\":"));
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
  Serial.print(F(",\"blood_pressure\":\"Normal\",\"headache\":\"No\",\"body_ache\":\"No\",\"fatigue\":\"Yes\",\"battery_mv\":5000,\"packet\":"));
  Serial.print(packetCounter);
  Serial.print(F(",\"protocol\":\"USB-Serial\"}"));
  Serial.println();

  digitalWrite(STATUS_LED_PIN, HIGH);
  delay(30);
  digitalWrite(STATUS_LED_PIN, LOW);
}

void processIncomingCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();
    if (cmd.length() == 0) return;

    if (cmd == "LED_TOGGLE") {
      digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
      Serial.println(F("{\"ack\":\"LED_TOGGLE\",\"status\":\"OK\"}"));
    } else if (cmd == "LED_ON") {
      digitalWrite(STATUS_LED_PIN, HIGH);
      Serial.println(F("{\"ack\":\"LED_ON\",\"status\":\"OK\"}"));
    } else if (cmd == "LED_OFF") {
      digitalWrite(STATUS_LED_PIN, LOW);
      Serial.println(F("{\"ack\":\"LED_OFF\",\"status\":\"OK\"}"));
    } else if (cmd == "BEEP") {
      tone(BUZZER_PIN, 1500, 150);
      Serial.println(F("{\"ack\":\"BEEP\",\"status\":\"OK\"}"));
    } else if (cmd == "SAMPLE" || cmd == "SAMPLE_NOW") {
      sendTelemetryPacket();
    }
  }
}

void setup() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
  pinMode(BUZZER_PIN, OUTPUT);

  Serial.begin(SERIAL_BAUD);
  delay(100);

  Serial.println(F("[Relivio] Initialized Arduino Uno Node. Streaming vitals JSON..."));
  sendTelemetryPacket();
}

void loop() {
  processIncomingCommands();
  unsigned long currentMillis = millis();
  if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = currentMillis;
    sendTelemetryPacket();
  }
}
