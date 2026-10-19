// Water Tank Monitor: 6 overhead tanks + 1 underground tank on ONE ESP32.
// Each tank has a JSN-SR04T waterproof ultrasonic sensor in its lid.
// The ESP32 serves a web page with every tank's level: open http://<ESP32 IP>/
// on any phone, PC or TV connected to the same WiFi. No server, app or internet.
//
// Also runs on a NodeMCU (ESP8266) for a 1-sensor prototype: pick the board in
// Arduino IDE and the right pins and libraries are used automatically.
//
// Arduino IDE + "esp32" (Espressif) or "esp8266" (ESP8266 Community) board package.
// No extra libraries needed. Board: "ESP32 Dev Module" or "NodeMCU 1.0 (ESP-12E Module)".
// See README.md for wiring.

#ifdef ESP8266
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
typedef ESP8266WebServer WebServer;
#else
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#endif
#include "page.h"

// ---------------- 1. WiFi (change these) ----------------
const char* WIFI_NAME     = "Office_WiFi";
const char* WIFI_PASSWORD = "wifi_password";

// If office WiFi is not reachable, the board makes its own WiFi network.
// Connect a phone to it and open http://192.168.4.1/
const char* OWN_WIFI_NAME     = "Tank-Monitor";
const char* OWN_WIFI_PASSWORD = "12345678";  // at least 8 characters

// ---------------- 2. Tanks (change these) ----------------
// emptyCm: sensor to tank BOTTOM in cm (the reading when the tank is empty)
// fullCm:  sensor to water surface when the tank is FULL, in cm.
//          Keep it 25 or more: JSN-SR04T cannot measure closer than ~25 cm.
// liters:  tank capacity in liters
struct Tank {
  const char* name;
  uint8_t trigPin;
  uint8_t echoPin;
  float emptyCm;
  float fullCm;
  float liters;
  int percent;  // filled in by the code, -1 = no reading (sensor/wiring problem)
};

#ifdef ESP8266
// NodeMCU prototype: one sensor. Trig on D1, Echo (through the 1k/2k resistors) on D2.
Tank tanks[] = {
  // name           TRIG ECHO emptyCm fullCm liters
  {"Test Tank",     D1,  D2,  150,    30,    1000},
};
#else
Tank tanks[] = {
  // name           TRIG ECHO emptyCm fullCm liters
  {"Overhead 1",    13,  34,  150,    30,    1000},
  {"Overhead 2",    14,  35,  150,    30,    1000},
  {"Overhead 3",    22,  18,  150,    30,    1000},
  {"Overhead 4",    23,  19,  150,    30,    1000},
  {"Overhead 5",    26,  32,  150,    30,    1000},
  {"Overhead 6",    27,  33,  150,    30,    1000},
  {"Underground",    4,  25,  250,    30,    10000},
};
#endif
const int TANK_COUNT = sizeof(tanks) / sizeof(tanks[0]);

const unsigned long READ_EVERY_MS = 1000;  // one tank per second, all 7 in ~7 s

WebServer server(80);

// ---------------- Sensor reading ----------------
// One ping. Returns distance in cm, or -1 if no echo.
float pingCm(const Tank& t) {
  digitalWrite(t.trigPin, LOW);
  delayMicroseconds(5);
  digitalWrite(t.trigPin, HIGH);
  delayMicroseconds(20);
  digitalWrite(t.trigPin, LOW);
  unsigned long us = pulseIn(t.echoPin, HIGH, 30000);  // 30 ms timeout = ~5 m
  if (us == 0) return -1;
  return us * 0.0343f / 2;
}

// Median of 5 pings, so one bad echo (splash, condensation drop) is ignored.
void readTank(Tank& t) {
  float r[5];
  int n = 0;
  for (int i = 0; i < 5; i++) {
    float d = pingCm(t);
    if (d > 0) r[n++] = d;
    delay(60);  // let the previous echo die out
  }
  if (n < 3) {
    t.percent = -1;
    return;
  }
  for (int i = 1; i < n; i++) {  // insertion sort, n <= 5
    float v = r[i];
    int j = i - 1;
    while (j >= 0 && r[j] > v) { r[j + 1] = r[j]; j--; }
    r[j + 1] = v;
  }
  float pct = (t.emptyCm - r[n / 2]) / (t.emptyCm - t.fullCm) * 100;
  t.percent = constrain((int)lroundf(pct), 0, 100);
}

// ---------------- Web page (HTML in page.h) ----------------

void handleData() {
  String json = "[";
  for (int i = 0; i < TANK_COUNT; i++) {
    if (i) json += ",";
    json += "{\"name\":\"" + String(tanks[i].name) + "\",\"percent\":" + String(tanks[i].percent) +
            ",\"liters\":" + String((long)tanks[i].liters) + "}";
  }
  json += "]";
  server.send(200, "application/json", json);
}

// ---------------- Setup / loop ----------------
void setup() {
  Serial.begin(115200);
  for (int i = 0; i < TANK_COUNT; i++) {
    pinMode(tanks[i].trigPin, OUTPUT);
    digitalWrite(tanks[i].trigPin, LOW);
    pinMode(tanks[i].echoPin, INPUT);
    tanks[i].percent = -1;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nOpen this on phone/PC/TV:  http://%s/\n", WiFi.localIP().toString().c_str());
    if (MDNS.begin("tanks")) Serial.println("Or (PC/iPhone):           http://tanks.local/");
  } else {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(OWN_WIFI_NAME, OWN_WIFI_PASSWORD);
    Serial.printf("\nOffice WiFi not found. Connect to WiFi \"%s\" and open http://%s/\n",
                  OWN_WIFI_NAME, WiFi.softAPIP().toString().c_str());
  }

  server.on("/", []() { server.send_P(200, "text/html", PAGE); });
  server.on("/data", handleData);
  server.begin();
}

void loop() {
  server.handleClient();
#ifdef ESP8266
  MDNS.update();
#endif

  static unsigned long lastRead = 0;
  static int next = 0;
  if (millis() - lastRead >= READ_EVERY_MS) {
    lastRead = millis();
    readTank(tanks[next]);
    Serial.printf("%-12s %4d%%\n", tanks[next].name, tanks[next].percent);
    next = (next + 1) % TANK_COUNT;
  }
}
