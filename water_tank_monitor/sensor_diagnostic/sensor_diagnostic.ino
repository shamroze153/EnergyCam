// Sensor DIAGNOSTIC: khud check karke batata hai ke masla kahan hai.
// Serial Monitor: 115200 baud. Har 10 second baad dobara check karta hai.

const int P[2] = {D1, D2};
const char* N[2] = {"D1", "D2"};

// Bina trigger ke pin kitni dafa badalta hai (sensor khud data bhej raha hai ya nahi)
int countChanges(int pin, unsigned long ms) {
  pinMode(pin, INPUT);
  int last = digitalRead(pin), n = 0;
  unsigned long t0 = millis();
  while (millis() - t0 < ms) {
    int v = digitalRead(pin);
    if (v != last) { n++; last = v; }
    yield();
  }
  return n;
}

// Ek dafa trigger bhej kar echo ka intezar
bool tryOnce(int trig, int echo, unsigned int pulseUs, float &cm) {
  pinMode(echo, INPUT);
  pinMode(trig, OUTPUT);
  digitalWrite(trig, LOW);
  delayMicroseconds(10);
  digitalWrite(trig, HIGH);
  delayMicroseconds(pulseUs);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 100000);
  pinMode(trig, INPUT);
  if (us == 0) return false;
  cm = us * 0.0343f / 2;
  return true;
}

void diagnose() {
  Serial.println("\n========== SENSOR DIAGNOSTIC ==========");

  pinMode(D1, INPUT);
  pinMode(D2, INPUT);
  delay(5);
  int idle1 = digitalRead(D1), idle2 = digitalRead(D2);
  Serial.printf("1) Aaram mein: D1=%d  D2=%d\n", idle1, idle2);

  int c1 = countChanges(D1, 700), c2 = countChanges(D2, 700);
  Serial.printf("2) Bina trigger ke badlaav: D1=%d  D2=%d\n", c1, c2);

  const unsigned int pulses[] = {10, 20, 50, 100, 500, 1000};
  int foundTrig = -1;
  unsigned int foundPulse = 0;
  float foundCm = 0;
  for (int ti = 0; ti < 2 && foundTrig < 0; ti++) {
    int ei = 1 - ti;
    for (unsigned int pw : pulses) {
      int ok = 0;
      float cm = 0, last = 0;
      for (int k = 0; k < 3; k++) {
        if (tryOnce(P[ti], P[ei], pw, cm)) { ok++; last = cm; }
        delay(60);
      }
      Serial.printf("3) TRIG=%s ECHO=%s pulse=%4u us -> %s", N[ti], N[ei], pw, ok ? "ECHO MILA" : "kuch nahi");
      if (ok) Serial.printf(" (%.1f cm, %d/3)", last, ok);
      Serial.println();
      if (ok >= 2) { foundTrig = ti; foundPulse = pw; foundCm = last; break; }
    }
  }

  Serial.println("---------------- NATEEJA ----------------");
  if (foundTrig == 0) {
    Serial.printf("OK! Wiring sahi hai, sensor chal raha hai. Faasla: %.1f cm\n", foundCm);
    if (foundPulse > 20) Serial.printf("Note: is sensor ko %u us ka trigger chahiye. Ye number mujhe bata dein.\n", foundPulse);
  } else if (foundTrig == 1) {
    Serial.println("Sensor theek hai, lekin NodeMCU par ORANGE aur GREEN ulte lage hain.");
    Serial.println("Hal: D1 aur D2 wale dono taar aapas mein badal dein.");
  } else if (c1 > 10 || c2 > 10) {
    Serial.println("Sensor ko bijli mil rahi hai aur wo khud data bhej raha hai (UART mode).");
    Serial.println("Hal: sensor par M1/M2/M3 / Mode pads khali hon. Ye nateeja mujhe bata dein.");
  } else if (idle2 == 1) {
    Serial.println("D2 hamesha HIGH hai: Echo ya 2k resistor wali line galat jagah (5V) se juri hai.");
    Serial.println("Hal: 2k resistor ka doosra sira GND (safed/kaale) wali line mein lagayein.");
  } else {
    Serial.println("Sensor bilkul jawab nahi de raha. Ye check karein:");
    Serial.println(" a) Sensor ko bijli: VCC -> VIN wali line, GND -> G wali line (kaan laga kar tik-tik sunein)");
    Serial.println(" b) Sensor RX -> orange wali line, Sensor TX -> 1k resistor wali line");
    Serial.println(" c) Kaali probe ki cable sensor board mein poori lagi ho");
  }
  Serial.println("==========================================");
}

void setup() {
  Serial.begin(115200);
  delay(300);
}

void loop() {
  diagnose();
  delay(10000);
}
