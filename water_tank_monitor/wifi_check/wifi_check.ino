// WIFI CHECK: batata hai NodeMCU WiFi se kyun nahi jur raha.
// 1) Aas paas ke 2.4 GHz WiFi dikhata hai  2) Jorne ki koshish karke wajah batata hai.
// Serial Monitor: 115200.

#include <ESP8266WiFi.h>

const char* WIFI_NAME     = "Aapke_WiFi_ka_naam";
const char* WIFI_PASSWORD = "Aapka_password";

const char* securityName(uint8_t t) {
  switch (t) {
    case ENC_TYPE_NONE: return "khula (bina password)";
    case ENC_TYPE_WEP:  return "WEP";
    case ENC_TYPE_TKIP: return "WPA";
    case ENC_TYPE_CCMP: return "WPA2";
    case ENC_TYPE_AUTO: return "WPA/WPA2";
    default:            return "doosra (WPA3/Enterprise?)";
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n===== WIFI CHECK =====");

  // Board khud restart ho raha ho to wajah yahan dikhti hai. RST button = "External System".
  String why = ESP.getResetReason();
  Serial.printf("Pichli dafa restart ki wajah: %s\n", why.c_str());
  if (why == "Power On") Serial.println("  (USB lagane par yahi aata hai. Bina USB nikaale baar baar aaye = bijli kam pari)");

  // WiFi ki taaqat thori kam: jurte waqt bijli ka jhatka kam lagta hai aur board restart nahi hota
  WiFi.persistent(false);
  WiFi.setOutputPower(12);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  Serial.println("Aas paas ke WiFi (NodeMCU sirf 2.4 GHz dekh sakta hai):");
  int n = WiFi.scanNetworks();
  int rssi = 0;
  bool found = false;
  for (int i = 0; i < n; i++) {
    bool match = WiFi.SSID(i) == WIFI_NAME;
    if (match && (!found || WiFi.RSSI(i) > rssi)) rssi = WiFi.RSSI(i);
    if (match) found = true;
    Serial.printf("  %s %-24s signal %4d  %s\n", match ? ">>" : "  ",
                  WiFi.SSID(i).c_str(), WiFi.RSSI(i), securityName(WiFi.encryptionType(i)));
  }
  Serial.printf("\nNodeMCU ka MAC address (IT maange to): %s\n", WiFi.macAddress().c_str());

  if (!found) {
    Serial.printf("\nNATEEJA: \"%s\" list mein nahi hai.\n", WIFI_NAME);
    Serial.println("Ya naam mein farq hai (capital/small, space), ya ye WiFi sirf 5 GHz par hai.");
    Serial.println("IT se kahein: is WiFi ko 2.4 GHz par bhi chala dein.");
    return;
  }

  Serial.printf("\n\"%s\" mil gaya (signal %d). Jorne ki koshish, 30 second tak", WIFI_NAME, rssi);
  WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && WiFi.status() != WL_WRONG_PASSWORD && millis() - t0 < 30000) {
    delay(500);
    Serial.print(".");
  }

  wl_status_t s = WiFi.status();
  Serial.print("\n\nNATEEJA: ");
  if (s == WL_CONNECTED) {
    Serial.printf("JUR GAYA! (%lu second laga) IP: %s\n", (millis() - t0) / 1000,
                  WiFi.localIP().toString().c_str());
  } else if (s == WL_WRONG_PASSWORD) {
    Serial.println("PASSWORD GHALAT hai. Capital/small letters aur @ wagaira dobara check karein.");
  } else {
    Serial.printf("Jur nahi saka (status %d).\n", s);
    if (rssi < -80) Serial.println("Signal bohat kamzor hai: NodeMCU ko router ke qareeb le jaayein.");
    else Serial.println("Shayad IT ne naye devices block kiye hain. Upar wala MAC address IT ko dein.");
  }
}

void loop() {}
