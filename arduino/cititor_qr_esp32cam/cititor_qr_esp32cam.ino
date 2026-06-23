/* =====================================================================
   cititor_qr_esp32cam.ino
   Modul de vedere - ESP32-CAM (AI Thinker)  -  recunoastere coduri QR
   ---------------------------------------------------------------------
   Rol in sistem:
     - capteaza imagini de la camera, decodeaza codul QR de pe cutie;
     - la fiecare cod valid trimite pe Serial:  "QR:<continut>\n"
       (ex. "QR:PKG-002"), pe care dashboard-ul PySide6 il citeste si
       il mapeaza la celula din dulap, apoi trimite comanda L<...> la
       Arduino.

   Biblioteca necesara (Library Manager):
     ESP32QRCodeReader  (autor: Alvaro Viebrantz)
     - include deja initializarea camerei + decodorul quirc.

   Setari placa in Arduino IDE:
     Board : "AI Thinker ESP32-CAM"
     PSRAM : Enabled
     (programare prin adaptor FTDI: GPIO0 la GND la upload)

   Nota: pinul GPIO4 = LED-ul alb de pe placa, folosit aici ca sursa de
   iluminare pentru a imbunatati contrastul codului QR (decodare mai
   stabila in lumina slaba).
   ===================================================================== */

#include "ESP32QRCodeReader.h"

ESP32QRCodeReader reader(CAMERA_MODEL_AI_THINKER);

/* ---------- iluminare ---------- */
#define PIN_LED       4        /* LED-ul alb de pe ESP32-CAM (AI Thinker) */
#define FOLOSESTE_LED true     /* pune false daca nu vrei LED-ul aprins */

/* ---------- anti-repetare (debounce) ---------- */
String ultimulCod = "";
unsigned long ultimulTimp = 0;
const unsigned long INTERVAL_REPETARE = 2000;  /* ms intre 2 trimiteri ale aceluiasi cod */

void onQrCodeTask(void *pvParameters) {
  struct QRCodeData qrCodeData;

  while (true) {
    if (reader.receiveQrCode(&qrCodeData, 100)) {
      if (qrCodeData.valid) {
        String cod = String((const char *)qrCodeData.payload);
        unsigned long acum = millis();

        /* trimite doar daca e cod nou sau a trecut suficient timp */
        if (cod != ultimulCod || (acum - ultimulTimp) > INTERVAL_REPETARE) {
          Serial.print("QR:");
          Serial.println(cod);
          ultimulCod = cod;
          ultimulTimp = acum;
        }
      }
    }
    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  if (FOLOSESTE_LED) {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, HIGH);   /* aprinde iluminarea pentru contrast QR */
  }

  Serial.println("ESP32-CAM cititor QR - pornire");
  reader.setup();
  reader.beginOnCore(1);           /* decodarea ruleaza pe core-ul 1 */

  xTaskCreate(onQrCodeTask, "onQrCode", 4096, NULL, 4, NULL);
  Serial.println("ESP32-CAM cititor QR - gata");
}

void loop() {
  /* toata munca se face in task-ul de mai sus */
  vTaskDelay(100 / portTICK_PERIOD_MS);
}
