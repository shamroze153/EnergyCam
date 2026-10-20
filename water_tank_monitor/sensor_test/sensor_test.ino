// Sensor test: sirf wiring check karne ke liye (WiFi nahi chahiye).
// Trig = D1, Echo = D2 (resistors ke zariye). Serial Monitor: 115200 baud.

const int TRIG = D1;
const int ECHO = D2;

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  digitalWrite(TRIG, LOW);
  Serial.println("\nSensor test shuru");
}

void loop() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(20);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 30000);  // 30 ms = ~5 m
  if (us == 0) {
    Serial.println("Echo nahi aaya: wiring check karein");
  } else {
    Serial.printf("Faasla: %.1f cm\n", us * 0.0343f / 2);
  }
  delay(500);
}
