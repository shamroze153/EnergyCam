// WIRE CHECK: breadboard ke taar khud check karta hai aur har 5 second mein
// OK / X ke saath batata hai kaunsa taar ghalat hai. Wiring wahi rahe
// (sensor 5V par, resistors lage hue). Serial Monitor: 115200.

const int TRIG = D1;
const int ECHO = D2;

void check() {
  Serial.println("\n----------- WIRE CHECK -----------");
  int bad = 0;

  // 1) Sensor ka RX khud HIGH rehta hai: D1 ko chhor kar dekhein
  pinMode(ECHO, INPUT);
  pinMode(TRIG, INPUT);
  int d1 = 0;
  for (int i = 0; i < 100; i++) { d1 += digitalRead(TRIG); delay(1); }
  Serial.print("1. Yellow (Trig) taar sensor tak:  ");
  if (d1 == 100) Serial.println("juda hai            OK");
  else { Serial.println("nahi pahunch raha   X  -> yellow aur orange ek hi line mein, orange D1 par"); bad++; }

  // 2) D1 aur D2 aapas mein jude to nahi? (3us ka pulse sensor ko nahi chalata)
  digitalWrite(TRIG, LOW);
  pinMode(TRIG, OUTPUT);
  int follows = 0;
  for (int i = 0; i < 10; i++) {
    digitalWrite(TRIG, HIGH); delayMicroseconds(3); int a = digitalRead(ECHO);
    digitalWrite(TRIG, LOW);  delayMicroseconds(3); int b = digitalRead(ECHO);
    if (a == HIGH && b == LOW) follows++;
    delay(20);
  }
  Serial.print("2. Trig aur Echo ki lines alag:    ");
  if (follows >= 8) { Serial.println("NAHI, judi hain      X  -> yellow wali line aur blue wali line ke beech ek khaali line chhorein"); bad++; }
  else Serial.println("haan                OK");

  // 3) D1 LOW ho to Echo (D2) aaram mein LOW honi chahiye
  delay(100);
  int d2 = 0;
  for (int i = 0; i < 300; i++) { d2 += digitalRead(ECHO); delay(1); }
  Serial.print("3. Echo line (D2) aaram mein:      ");
  if (d2 == 0) Serial.println("LOW                 OK");
  else if (d2 < 300) Serial.println("hil rahi hai        ?  (sensor khud kuch bhej raha hai)");
  else {
    // 5us ke liye D2 ko LOW kheench kar dekhein: seedhi bijli hai ya resistor ke zariye?
    pinMode(ECHO, OUTPUT);
    digitalWrite(ECHO, LOW);
    delayMicroseconds(5);
    int still = digitalRead(ECHO);
    pinMode(ECHO, INPUT);
    if (still) Serial.println("hamesha HIGH        X  -> green/D2 wali line red (5V) wali line se chhoo rahi hai");
    else       Serial.println("hamesha HIGH        X  -> 2k resistor ka doosra sira GND (black/white) line mein lagayein");
    bad++;
  }

  // 4) Asli test: sensor jawab deta hai?
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(20);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 60000);
  Serial.print("4. Sensor ka jawab:                ");
  if (us >= 100) Serial.printf("%.1f cm             OK\n", us * 0.0343f / 2);
  else           Serial.println("nahi aaya            X");
  digitalWrite(LED_BUILTIN, us >= 100 ? LOW : HIGH);

  if (bad) Serial.println("\nUpar X wali line theek karein. Ye check har 5 second mein khud dobara chalega.");
  else if (us < 100) Serial.println("\nSaare taar theek hain, phir bhi jawab nahi: sensor ya us ka safed plug kharab hai.");
  else Serial.println("\nSab theek! Sensor chal raha hai.");
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1500);  // sensor ko jaagne ka waqt
}

void loop() {
  check();
  delay(5000);
}
