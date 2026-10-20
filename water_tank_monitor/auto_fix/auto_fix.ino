// AUTO FIX: sensor se baat karne ke 20 tareeqay khud try karta hai.
// Jo tareeqa chal jaaye us par ruk jaata hai aur har second cm dikhata hai
// (NodeMCU ki neeli LED jalti hai). Wiring wahi rahe: sensor 5V par (VU),
// Trig -> D1, Echo resistors se -> D2. Serial Monitor: 115200, phir RST dabayein.

#include <SoftwareSerial.h>

const int PIN_D1 = D1;
const int PIN_D2 = D2;

// Jo tareeqa chala (kind -1 = abhi koi nahi)
// kind 0 = trigger, 1 = trigger (open-drain), 2 = serial 0x55, 3 = serial khud bolta hai
int kind = -1, trigPin, echoPin, width;

// Trigger mode: ek ping. Echo ki lambai (us) ya 0.
unsigned long pingTrigger(int trig, int echo, int us, bool openDrain) {
  pinMode(echo, INPUT);
  pinMode(trig, OUTPUT);
  digitalWrite(trig, LOW);
  delayMicroseconds(5);
  if (openDrain) pinMode(trig, INPUT);  // chhor do: sensor ka pull-up line ko 5V tak le jaata hai
  else digitalWrite(trig, HIGH);
  delayMicroseconds(us);
  pinMode(trig, OUTPUT);
  digitalWrite(trig, LOW);
  unsigned long t = pulseIn(echo, HIGH, 60000);
  return t >= 100 ? t : 0;
}

// Serial mode (9600): 0xFF, H, L, SUM. Faasla mm mein, ya -1.
int pingSerial(int tx, int rx, bool sendTrigger) {
  SoftwareSerial ss(rx, tx);
  ss.begin(9600);
  delay(5);
  while (ss.available()) ss.read();
  if (sendTrigger) ss.write(0x55);
  uint8_t buf[4];
  int n = 0;
  unsigned long start = millis();
  while (millis() - start < 300) {
    while (ss.available()) {
      uint8_t c = ss.read();
      if (n == 0 && c != 0xFF) continue;
      buf[n++] = c;
      if (n == 4) {
        if (((buf[0] + buf[1] + buf[2]) & 0xFF) == buf[3]) { ss.end(); return buf[1] * 256 + buf[2]; }
        n = 0;
      }
    }
    yield();
  }
  ss.end();
  return -1;
}

// Locked tareeqe se faasla cm mein, ya -1
float readCm() {
  if (kind <= 1) {
    unsigned long t = pingTrigger(trigPin, echoPin, width, kind == 1);
    return t ? t * 0.0343f / 2 : -1;
  }
  int mm = pingSerial(trigPin, echoPin, kind == 2);
  return mm >= 0 ? mm / 10.0f : -1;
}

const char* KIND_NAME[] = {"trigger", "trigger open-drain", "serial 0x55", "serial khud"};

bool tryMethod(int k, int trig, int echo, int w, int num) {
  kind = k; trigPin = trig; echoPin = echo; width = w;
  Serial.printf("Tareeqa %2d/20: %-18s trig=%s echo=%s", num, KIND_NAME[k],
                trig == PIN_D1 ? "D1" : "D2", echo == PIN_D1 ? "D1" : "D2");
  if (k <= 1) Serial.printf(" %4dus", w);
  for (int i = 0; i < 2; i++) {
    float cm = readCm();
    delay(80);
    if (cm >= 0) { Serial.printf("  -> MIL GAYA! %.1f cm\n", cm); return true; }
  }
  Serial.println("  -> nahi");
  return false;
}

bool searchAll() {
  const int normalW[] = {10, 20, 50, 200, 1000};
  const int odW[] = {20, 200, 1000};
  int num = 0;
  for (int order = 0; order < 2; order++) {
    int trig = order == 0 ? PIN_D1 : PIN_D2;
    int echo = order == 0 ? PIN_D2 : PIN_D1;
    for (int w : normalW) if (tryMethod(0, trig, echo, w, ++num)) return true;
    for (int w : odW)     if (tryMethod(1, trig, echo, w, ++num)) return true;
    if (tryMethod(2, trig, echo, 0, ++num)) return true;
    if (tryMethod(3, trig, echo, 0, ++num)) return true;
  }
  kind = -1;
  return false;
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(PIN_D1, INPUT);
  pinMode(PIN_D2, INPUT);
  delay(800);  // sensor ko jaagne ka waqt
  Serial.println("\n\n===== AUTO FIX =====");

  // Info: sensor ka RX aam tor par khud HIGH rehta hai. D1 HIGH mile = yellow taar D1 se juda hai.
  int highs = 0;
  for (int i = 0; i < 50; i++) { highs += digitalRead(PIN_D1); delay(2); }
  Serial.printf("INFO: D1 akela %s\n", highs == 50 ? "HIGH (yellow taar juda lagta hai)" :
                                     highs == 0  ? "LOW" : "hil raha hai");
  Serial.printf("INFO: D2 akela %s\n\n", digitalRead(PIN_D2) ? "HIGH" : "LOW");
}

void loop() {
  if (kind < 0) {
    if (!searchAll()) {
      Serial.println("\nNATEEJA: 20 mein se koi tareeqa nahi chala.");
      Serial.println("Code ki taraf se sab try ho gaya. Masla kisi taar ya sensor mein hai.");
      Serial.println("Is screen ka screenshot bhejein. 10 second baad dobara try karega...\n");
      delay(10000);
      return;
    }
    Serial.println("\nYahi tareeqa rakh liya. Ab har second faasla:\n");
  }

  float cm = readCm();
  digitalWrite(LED_BUILTIN, cm >= 0 ? LOW : HIGH);
  if (cm < 0)        Serial.println("echo nahi aaya (haath sensor ke saamne 30-100 cm par rakhein)");
  else if (cm > 600) Serial.println("sensor chal raha hai, saamne kuch nahi mila");
  else               Serial.printf("Faasla: %.1f cm\n", cm);
  delay(1000);
}
