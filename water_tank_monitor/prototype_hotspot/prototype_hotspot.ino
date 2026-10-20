// Tank level prototype (NodeMCU / ESP8266), sirf apne WiFi par: office WiFi ki zaroorat nahi.
// Phone ko WiFi "Tank-Monitor" (password 12345678) se jorein aur http://192.168.4.1 kholein.

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

const int TRIG = D1;
const int ECHO = D2;
const float EMPTY_CM = 100;  // sensor se tank ke bottom tak (test ke liye 100 cm)
const float FULL_CM  = 25;   // sensor se full pani tak (kam az kam 25)

ESP8266WebServer server(80);
float distanceCm = -1;
int percent = -1;

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

// 5 dafa naap kar beech wali value lo, taake ek galat reading ka asar na ho
void readSensor() {
  float r[5];
  int n = 0;
  for (int i = 0; i < 5; i++) {
    float d = pingCm();
    if (d > 0) r[n++] = d;
    delay(60);
  }
  if (n < 3) { distanceCm = -1; percent = -1; return; }
  for (int i = 1; i < n; i++) {
    float v = r[i];
    int j = i - 1;
    while (j >= 0 && r[j] > v) { r[j + 1] = r[j]; j--; }
    r[j + 1] = v;
  }
  distanceCm = r[n / 2];
  float p = (EMPTY_CM - distanceCm) / (EMPTY_CM - FULL_CM) * 100;
  percent = constrain((int)lroundf(p), 0, 100);
}

void handleRoot() {
  String color = percent < 25 ? "#e5534b" : percent < 50 ? "#e3a21a" : "#35b26b";
  String html = "<!doctype html><html><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<meta http-equiv='refresh' content='2'><title>Tank Level</title>"
                "<style>body{font-family:sans-serif;background:#f2f4f7;text-align:center;margin:0;padding:24px}"
                ".tank{width:140px;height:260px;margin:20px auto;border-radius:16px;background:#e2e7ed;position:relative;overflow:hidden}"
                ".water{position:absolute;left:0;right:0;bottom:0}.pct{font-size:56px;font-weight:bold}</style></head><body>"
                "<h2>Test Tank</h2>";
  if (percent < 0) {
    html += "<div class='tank'></div><div class='pct' style='color:#e5534b'>--</div><p>Sensor check karein (echo nahi aa raha)</p>";
  } else {
    html += "<div class='tank'><div class='water' style='height:" + String(percent) + "%;background:" + color + "'></div></div>";
    html += "<div class='pct' style='color:" + color + "'>" + String(percent) + "%</div>";
    html += "<p>Faasla: " + String(distanceCm, 1) + " cm</p>";
  }
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  digitalWrite(TRIG, LOW);
  pinMode(ECHO, INPUT);

  WiFi.mode(WIFI_AP);
  WiFi.softAP("Tank-Monitor", "12345678");
  Serial.println("\nPhone ko WiFi 'Tank-Monitor' (password 12345678) se jorein aur http://192.168.4.1 kholein");
  server.on("/", handleRoot);
  server.begin();
}

void loop() {
  server.handleClient();
  static unsigned long last = 0;
  if (millis() - last > 1000) {
    last = millis();
    readSensor();
    if (percent < 0) Serial.println("Echo nahi aaya: sensor check karein");
    else Serial.printf("Faasla: %.1f cm   Level: %d%%\n", distanceCm, percent);
  }
}
