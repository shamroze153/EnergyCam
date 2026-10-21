// 140-H Underground Tank: live water level dashboard (NodeMCU / ESP8266 + JSN-SR04T).
// Phone ko WiFi "Tank-Monitor" (password 12345678) se jorein aur http://192.168.4.1 kholein.
// Office WiFi allow ho jaaye to WIFI_NAME / WIFI_PASSWORD bhar dein; na jure to
// Tank-Monitor khud chal jaata hai.
// Wiring: Trig D1, Echo 1k/2k resistors se D2, sensor 5V (VU). Serial Monitor: 115200.
// Dashboard ka design page.h mein hai.

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include "page.h"

// ---------------- WiFi ----------------
const char* WIFI_NAME     = "";  // khaali = sirf Tank-Monitor
const char* WIFI_PASSWORD = "";
const char* OWN_WIFI_NAME     = "Tank-Monitor";
const char* OWN_WIFI_PASSWORD = "12345678";  // kam az kam 8 characters

// ---------------- Tank (yahan apne tank ke naap) ----------------
const char* TANK_NAME       = "140-H Underground Tank";
const float TANK_DEPTH_CM   = 122;  // 4 ft: dhakkan se tank ke bottom tak
const float MAX_WATER_CM    = 107;  // 3.5 ft: full hone par pani ki unchai
const float SENSOR_ABOVE_CM = 0;    // sensor dhakkan se kitna upar (PVC pipe par lagayein to 15)
const float CAPACITY_LITERS = 0;    // full (MAX_WATER_CM) par kitne liter; 0 = liters na dikhayein
const int   LOW_PERCENT     = 25;   // is se kam = "Low water" alarm

const int TRIG = D1;
const int ECHO = D2;

ESP8266WebServer server(80);

bool ok = false;           // sensor ki taaza reading hai?
float distanceCm = 0;      // sensor se pani tak
float waterCm = 0;         // pani ki unchai (bottom se)
int percent = 0;           // MAX_WATER_CM ka kitna %
unsigned long lastGood = 0;

// Har minute ka % (pichle 60 minute), -1 = reading nahi thi
const int HIST = 60;
int8_t hist[HIST];
int histCount = 0;

float pingCm() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(20);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 30000);
  if (us == 0) return -1;
  return us * 0.0343f / 2;
}

// 5 dafa naap kar beech wali value, taake ek ghalat reading ka asar na ho
void readSensor() {
  float r[5];
  int n = 0;
  for (int i = 0; i < 5; i++) {
    float d = pingCm();
    if (d > 0) r[n++] = d;
    delay(60);
  }
  if (n < 3) {
    if (millis() - lastGood > 10000) ok = false;  // 10 s tak koi echo nahi
    return;
  }
  for (int i = 1; i < n; i++) {
    float v = r[i];
    int j = i - 1;
    while (j >= 0 && r[j] > v) { r[j + 1] = r[j]; j--; }
    r[j + 1] = v;
  }
  distanceCm = r[n / 2];
  waterCm = constrain(TANK_DEPTH_CM + SENSOR_ABOVE_CM - distanceCm, 0.0f, TANK_DEPTH_CM);
  percent = constrain((int)lroundf(waterCm / MAX_WATER_CM * 100), 0, 100);
  ok = true;
  lastGood = millis();
}

void pushHistory() {
  int8_t v = ok ? percent : -1;
  if (histCount < HIST) {
    hist[histCount++] = v;
  } else {
    memmove(hist, hist + 1, HIST - 1);
    hist[HIST - 1] = v;
  }
}

void handleData() {
  String j;
  j.reserve(420);
  j = "{\"name\":\"";
  j += TANK_NAME;
  j += "\",\"ok\":";
  j += ok ? "true" : "false";
  j += ",\"pct\":" + String(percent);
  j += ",\"waterCm\":" + String(waterCm, 1);
  j += ",\"distCm\":" + String(distanceCm, 1);
  j += ",\"depthCm\":" + String(TANK_DEPTH_CM, 0);
  j += ",\"maxCm\":" + String(MAX_WATER_CM, 0);
  j += ",\"cap\":" + String(CAPACITY_LITERS, 0);
  j += ",\"low\":" + String(LOW_PERCENT);
  j += ",\"hist\":[";
  for (int i = 0; i < histCount; i++) {
    if (i) j += ",";
    j += String(hist[i]);
  }
  j += "]}";
  server.send(200, "application/json", j);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  digitalWrite(TRIG, LOW);
  pinMode(ECHO, INPUT);

  bool joined = false;
  if (strlen(WIFI_NAME) > 0) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
    Serial.print("\nWiFi se jur raha hai");
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
      delay(500);
      Serial.print(".");
    }
    joined = WiFi.status() == WL_CONNECTED;
  }
  if (joined) {
    Serial.printf("\nDashboard: http://%s/\n", WiFi.localIP().toString().c_str());
  } else {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(OWN_WIFI_NAME, OWN_WIFI_PASSWORD);
    Serial.printf("\nPhone ko WiFi '%s' (password %s) se jorein aur http://192.168.4.1 kholein\n",
                  OWN_WIFI_NAME, OWN_WIFI_PASSWORD);
  }

  server.on("/", []() { server.send_P(200, "text/html", PAGE); });
  server.on("/data", handleData);
  server.begin();
}

void loop() {
  server.handleClient();

  static unsigned long lastRead = 0, lastHist = 0;
  if (millis() - lastRead >= 1000) {
    lastRead = millis();
    readSensor();
    if (ok) Serial.printf("Pani: %.1f cm (%.2f ft)   Level: %d%%\n", waterCm, waterCm / 30.48, percent);
    else Serial.println("Echo nahi aaya: sensor check karein");
  }
  if (lastHist == 0 || millis() - lastHist >= 60000) {
    lastHist = millis();
    pushHistory();
  }
}
