# Water Tank Monitor (6 overhead + 1 underground)

**Sab se sasta aur aasaan system:** ek ESP32 board aur 7 waterproof sensors.
ESP32 khud ek web page banata hai jis par saare tanks ka level % aur liters
dikhte hain. Ye page office WiFi par kisi bhi **phone, PC ya TV ke browser**
mein khul jaata hai. Koi server, app, Raspberry Pi ya internet nahi chahiye.

Rang ka matlab: **Green** 50% se upar, **Orange** 25–50%, **Red** 25% se kam
("Pani kam hai"). Agar kisi sensor ki reading nahi aa rahi to us tank par
"Sensor check karein" likha aata hai.

**3D video guide:** `3d_guide.html` browser mein kholein. Parts, breadboard
wiring, code upload, test aur tank par lagana, sab step by step 3D mein hai.

## 1. Shopping list (andaze ki qeemat, market mein check kar lein)

| Cheez | Tadaad | Approx |
|---|---|---|
| ESP32 DevKit board (30 ya 38 pin) | 1 | Rs 1,200–1,800 |
| JSN-SR04T waterproof ultrasonic sensor | 7 | Rs 1,500–2,200 har ek |
| Resistor 1k ohm | 7 | Rs 50 total |
| Resistor 2k ohm (ya 2.2k) | 7 | Rs 50 total |
| 5V 2A adapter (purana mobile charger + USB cable bhi chalega) | 1 | Rs 500 |
| CAT6 / LAN cable (har sensor se ESP32 box tak) | zaroorat ke mutabiq | Rs 60–100 / meter |
| Plastic waterproof box, veroboard, jumper wires | 1 set | Rs 800 |

**Total: approx Rs 15,000–22,000** (cable ki lambai par depend karta hai).

## 2. Wiring

Har JSN-SR04T sensor ke 4 taar hote hain: **5V, Trig, Echo, GND**.

```
Sensor 5V   ──────────────► ESP32 5V (VIN)
Sensor GND  ──────────────► ESP32 GND
Sensor Trig ──────────────► ESP32 TRIG pin (table dekhein)
Sensor Echo ──[ 1k ]──┬───► ESP32 ECHO pin (table dekhein)
                      │
                    [ 2k ]
                      │
                     GND
```

Echo par 1k aur 2k ke resistor zaroor lagayein. Sensor 5V ka signal deta
hai aur ESP32 sirf 3.3V bardasht karta hai. Resistors ke baghair board
dheere dheere kharab ho sakta hai.

| Tank | TRIG pin | ECHO pin |
|---|---|---|
| Overhead 1 | GPIO 13 | GPIO 34 |
| Overhead 2 | GPIO 14 | GPIO 35 |
| Overhead 3 | GPIO 22 | GPIO 18 |
| Overhead 4 | GPIO 23 | GPIO 19 |
| Overhead 5 | GPIO 26 | GPIO 32 |
| Overhead 6 | GPIO 27 | GPIO 33 |
| Underground | GPIO 4 | GPIO 25 |

Saare sensors ke 5V aur GND aapas mein jor kar ESP32 ke 5V aur GND par
lagayein. ESP32 ko 5V 2A adapter se bijli dein.

**Lambi cable:** sensor ka chhota board (jis par 4 pin hain) tank ke paas
rakhein aur us se ESP32 box tak CAT6 cable chalayein (CAT6 ki 4 taarein:
5V, GND, Trig, Echo). 20–30 meter tak aam tor par theek chalta hai.

## 3. Sensor tank par kaise lagayein

- Tank ke dhakkan mein surakh karein aur sensor ka munh **seedha neeche
  pani ki taraf** rakhein.
- Sensor full level se **kam az kam 25 cm upar** hona chahiye, kyunke is se
  qareeb wo naap nahi sakta.
- Inlet pipe, float valve ya tank ki deewar ke bilkul saath na lagayein,
  warna galat echo aata hai.

## 4. Code upload karna (sirf ek dafa)

1. Computer par **Arduino IDE** install karein (arduino.cc).
2. *Tools > Board > Boards Manager* mein "esp32" search karke
   **esp32 by Espressif** install karein.
3. Ye folder (`water_tank_monitor`) Arduino IDE mein kholein: file
   `water_tank_monitor.ino`.
4. Code ke upar wale hisse mein ye cheezein badlein:
   - `WIFI_NAME` aur `WIFI_PASSWORD`: office WiFi ka naam aur password
   - har tank ki line mein `emptyCm`, `fullCm` aur `liters` (step 5 dekhein)
   - tank ke naam bhi badal sakte hain, jaise `"Block A Roof"`
5. *Tools > Board* mein **ESP32 Dev Module** select karein, USB cable lagayein,
   aur **Upload** dabayein.
6. *Tools > Serial Monitor* kholein (115200). Wahan aisi line aayegi:
   `Open this on phone/PC/TV:  http://192.168.1.50/`

Bas, wo address office ke TV, PC ya phone ke browser mein kholein. Page har
5 second mein khud refresh hota hai.

**Agar office WiFi nahi milta** to ESP32 apna WiFi bana leta hai jiska naam
`Tank-Monitor` aur password `12345678` hai. Phone ko us WiFi se connect
karein aur `http://192.168.4.1/` kholein.

**Tip:** router mein ESP32 ke liye "DHCP reservation" kar dein taake uska IP
address kabhi na badle.

## 5. Calibration (har tank ke liye 2 naap)

Measuring tape se ye 2 cheezein naapein:

- **`emptyCm`**: sensor ke munh se tank ke **bottom** tak ka faasla (cm)
- **`fullCm`**: sensor ke munh se **full pani** (overflow pipe ke level) tak
  ka faasla (cm)

Misal: tank 150 cm gehra hai aur sensor ke 30 cm neeche overflow hai. To:

```cpp
{"Overhead 1", 13, 34, 150, 30, 1000},
```

## NodeMCU (ESP8266) se 1 sensor ka prototype

Agar aapke paas NodeMCU (ESP8266, board par "ESP-12E" likha hota hai) hai to 1 tank
ka test bilkul isi code se ho jaayega. Arduino IDE mein board **NodeMCU 1.0
(ESP-12E Module)** chunein (Boards Manager se "esp8266" package install karein).
Code khud NodeMCU wale pins le lega.

| Sensor pin | NodeMCU |
|---|---|
| 5V | VIN (LoLin "NodeMCU V3" board par **VU**) |
| GND | G |
| Trig | D1 |
| Echo | 1k resistor → D2, aur D2 se 2k resistor → G |

- Agar 1k aur 2k nahi hain to **ek hi value ke 3 resistor** lein (jaise teeno 1k ya
  teeno 10k): 1 resistor Echo se D2 tak, aur 2 resistor series mein D2 se G tak.
- LoLin "NodeMCU V3" (chauda board, CH340 chip) par VIN pin USB se 5V nahi deta;
  wahan sensor ka 5V **VU** pin se lein (A0 ki taraf se 3rd pin). Tik-tik na aaye to
  sab se pehle yahi check karein.
- NodeMCU ke pins ESP32 se kam hain, is liye saare 7 tanks ke liye ESP32 hi lein.

## 6. Masle aur hal

| Masla | Hal |
|---|---|
| "Sensor check karein" aata hai | Us sensor ke 4 taar aur resistors check karein. Serial Monitor mein `-1%` aayega. |
| Reading oopar neeche hoti hai | Sensor ko seedha karein aur inlet pipe se door lagayein. |
| Underground tank ki reading galat hai | Underground tank mein bhaap (condensation) sensor par paani ke qatre jama kar deti hai. Sensor ko kabhi kabhi saaf karein. Phir bhi masla rahe to wahan pressure sensor lagwana parega. |
| Underground tank bohat door hai (30 m se zyada) | Wahan ek doosra ESP32 lagayein aur yahi code dalein, `tanks[]` mein sirf `"Underground"` ki line rakhein. Us ka apna alag page hoga. |
| Page nahi khulta | Phone ya TV usi WiFi par hona chahiye jis par ESP32 hai. Serial Monitor mein IP check karein. |
