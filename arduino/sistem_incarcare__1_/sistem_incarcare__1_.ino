#include <AccelStepper.h>
#include <Servo.h>

// ---- Servomotoare ----
Servo servoBaza, servoUmar, servoCot, servoAntebrat, servoGripper;
const int PIN_BAZA = 3, PIN_UMAR = 5, PIN_COT = 6, PIN_ANTEBRAT = 9, PIN_GRIPPER = 10;

// ---- Motoare pas cu pas (drivere A4988, mod DRIVER) ----
AccelStepper motor1(AccelStepper::DRIVER, 2, 4);   // translatie pe coloana
AccelStepper motor2(AccelStepper::DRIVER, 7, 8);   // deplasare pe rand

// ---- Constante de pozitionare (se calibreaza pe structura reala) ----
const long PASI_COLOANA = 400;   // pasi intre doua coloane
const long PASI_RAND    = 300;   // pasi intre doua randuri
const int  GRIPPER_DESCHIS = 90;
const int  GRIPPER_INCHIS  = 20;

void setup() {
  Serial.begin(9600);
  servoBaza.attach(PIN_BAZA);
  servoUmar.attach(PIN_UMAR);
  servoCot.attach(PIN_COT);
  servoAntebrat.attach(PIN_ANTEBRAT);
  servoGripper.attach(PIN_GRIPPER);
  pozitieRepaus();

  motor1.setMaxSpeed(800);  motor1.setAcceleration(400);
  motor2.setMaxSpeed(800);  motor2.setAcceleration(400);

  Serial.println("Sistem pregatit");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 4 && cmd.charAt(0) == 'L') {
      int dulap   = cmd.charAt(1) - '0';
      int coloana = cmd.charAt(2) - '0';
      int rand    = cmd.charAt(3) - '0';
      executaIncarcare(dulap, coloana, rand);
      Serial.println("OK");
    }
  }
}

void executaIncarcare(int dulap, int coloana, int rand) {
  motor1.runToNewPosition((long)coloana * PASI_COLOANA);   // 1. coloana
  motor2.runToNewPosition((long)rand * PASI_RAND);         // 2. rand
  miscareBrat(dulap);                                      // 3. extindere brat
  servoGripper.write(GRIPPER_INCHIS);  delay(500);         // 4. apucare colet
  pozitieRepaus();                                         // 5. retragere brat
  motor2.runToNewPosition(0);                              // 6. revenire rand
  motor1.runToNewPosition(0);                              // 7. revenire coloana
  servoGripper.write(GRIPPER_DESCHIS); delay(500);         // 8. eliberare colet
}

void pozitieRepaus() {
  servoBaza.write(90);
  servoUmar.write(90);
  servoCot.write(90);
  servoAntebrat.write(90);
}

void miscareBrat(int dulap) {
  servoBaza.write(dulap == 0 ? 45 : 135);   // orientare spre dulapul ales
  servoUmar.write(120);
  servoCot.write(60);
  servoAntebrat.write(90);
  delay(700);
}