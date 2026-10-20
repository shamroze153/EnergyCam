// HARDWARE TESTER (seedha 3.3V setup: grey taar 3V par, resistors nahi).
// Shuru mein 2 check khud karta hai, phir har second:
//   SENSOR: tik + echo -> cm. Echo aaye to NodeMCU ki neeli LED jalti hai.
//   PROBE:  ek faltu jumper ka female sira A0 pin par lagayein, male sira
//           breadboard ke kisi khaane mein. Code batata hai us khaane mein kya hai.
// 5V (VU) setup ke saath probe na lagayein. Serial Monitor: 115200.

const int TRIG = D1;
const int ECHO = D2;

// A0 ki average voltage, ms milliseconds tak (NodeMCU A0: 0 - 3.2V)
float probeVolts(int ms) {
  long sum = 0;
  int n = ms / 5;
  for (int i = 0; i < n; i++) { delay(5); sum += analogRead(A0); }
  return sum * 3.2f / 1023.0f / n;
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  digitalWrite(TRIG, LOW);
  pinMode(ECHO, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  Serial.println("\n\n===== HARDWARE TESTER =====");

  // CHECK 1: sensor ka TX (D2) aam tor par LOW rehta hai
  int highs = 0;
  for (int i = 0; i < 100; i++) { highs += digitalRead(ECHO); delay(2); }
  Serial.print("CHECK 1 (D2 / blue taar): ");
  if (highs == 100) Serial.println("hamesha HIGH -> blue/green khaana red/grey se chhoo raha hai");
  else              Serial.println("theek");

  // CHECK 2: D1 aur D2 aapas mein judey to nahi (3us ke trigger par sensor nahi bolta)
  int follows = 0;
  for (int i = 0; i < 5; i++) {
    digitalWrite(TRIG, HIGH); delayMicroseconds(3); int a = digitalRead(ECHO);
    digitalWrite(TRIG, LOW);  delayMicroseconds(3); int b = digitalRead(ECHO);
    if (a == HIGH && b == LOW) follows++;
    delay(100);
  }
  Serial.print("CHECK 2 (D1-D2 short):    ");
  if (follows == 5) Serial.println("D1 aur D2 judey hain -> yellow aur blue alag khaanon mein lagayein");
  else              Serial.println("theek");
  Serial.println("Ab probe (A0 wala taar) ek ek khaane mein lagayein:\n");
}

void loop() {
  // SENSOR: 50us trigger, phir echo ka intezar
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(50);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 60000);
  digitalWrite(LED_BUILTIN, us ? LOW : HIGH);  // LED jale = sensor theek
  delay(100);

  // PROBE: D1 thori der HIGH phir LOW; A0 dono dafa naapta hai
  digitalWrite(TRIG, HIGH);
  float vHigh = probeVolts(200);
  digitalWrite(TRIG, LOW);
  float vLow = probeVolts(200);

  Serial.print("SENSOR: ");
  if (us) Serial.printf("OK! %5.1f cm    ", us * 0.0343f / 2);
  else    Serial.print("echo nahi aaya   ");
  Serial.printf("| PROBE: %.1fV/%.1fV -> ", vHigh, vLow);
  if (vHigh > 2.5 && vLow > 2.5)      Serial.println("3.3V khaana (red + grey) - bijli aa rahi hai");
  else if (vHigh > 2.5 && vLow < 0.6) Serial.println("D1 khaana (yellow + orange) - trig pahunch raha hai");
  else if (vHigh < 0.3 && vLow < 0.3) Serial.println("0V (GND ya D2 khaana, ya probe khaali)");
  else                                Serial.println("beech ki voltage -> taar dheela ya ghalat khaana");
  delay(400);
}
