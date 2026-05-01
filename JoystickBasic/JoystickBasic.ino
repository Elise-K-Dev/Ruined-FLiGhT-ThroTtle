#include <RotaryEncoder.h>

// Pin definitions
const int pinX = A1; // VRx pin
const int pinY = A0; // VRy pin
const int pinX2 = A2; // second joystick VRx pin
const int pinY2 = A3; // second joystick VRy pin
const int pinSW1 = 13; // first joystick SW pin
const int pinSW2 = 12; // second joystick SW pin
const int pinToggle = 11; // two-position switch pin
const int pinEncCLK = 2; // rotary encoder CLK pin
const int pinEncDT = 3; // rotary encoder DT pin
const int pinEncSW = 10; // rotary encoder SW pin
const int deadzone = 35;
const int loopSamples = 2;
const int outputMax = 100;
const unsigned long throttleSlowIntervalUs = 2000;
const unsigned long throttleFastIntervalUs = 20;
const int throttleFullPushStep = 5;
const unsigned long serialPrintIntervalMs = 20;

RotaryEncoder encoder(pinEncCLK, pinEncDT, RotaryEncoder::LatchMode::TWO03);

int centerX = 512;
int centerY = 512;
const int fixedMinX = 0;
const int fixedCenterX = 502;
const int fixedMaxX = 1023;
const int fixedMinY = 0;
const int fixedCenterY = 521;
const int fixedMaxY = 1023;
const int fixedMinX2 = 0;
const int fixedCenterX2 = 510;
const int fixedMaxX2 = 1023;
const int fixedMinY2 = 133;
const int fixedCenterY2 = 512;
const int fixedMaxY2 = 931;

int throttleValue = 0;
int encoderDelta = 0;
long lastEncoderPosition = 0;
unsigned long lastThrottleUpdateUs = 0;
unsigned long lastSerialPrintMs = 0;

int readAverage(int pin, int samples) {
  analogRead(pin);
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
  }
  return sum / samples;
}

int normalizeAxis(int raw, int center, int minValue, int maxValue) {
  int diff = raw - center;
  if (diff > -deadzone && diff < deadzone) {
    return 0;
  }

  if (diff > 0) {
    int range = maxValue - center - deadzone;
    if (range < 1) {
      range = 1;
    }
    return constrain(map(diff - deadzone, 0, range, 0, outputMax), 0, outputMax);
  }

  int range = center - minValue - deadzone;
  if (range < 1) {
    range = 1;
  }
  return constrain(map(diff + deadzone, -range, 0, -outputMax, 0), -outputMax, 0);
}

void updateIncrementalThrottle(int yValue) {
  int amount = abs(yValue);
  if (amount == 0) {
    return;
  }

  unsigned long now = micros();
  long inverseAmount = outputMax - amount;
  long curve = inverseAmount * inverseAmount;
  unsigned long intervalUs = throttleFastIntervalUs +
      ((throttleSlowIntervalUs - throttleFastIntervalUs) * curve / (outputMax * outputMax));
  if (now - lastThrottleUpdateUs < intervalUs) {
    return;
  }
  lastThrottleUpdateUs = now;

  int step = amount >= 90 ? throttleFullPushStep : 1;
  if (yValue > 0) {
    throttleValue += step;
  } else {
    throttleValue -= step;
  }

  throttleValue = constrain(throttleValue, 0, 100);
}

void readEncoder() {
  long newPosition = encoder.getPosition();
  long movement = newPosition - lastEncoderPosition;
  if (movement != 0) {
    encoderDelta += movement;
    lastEncoderPosition = newPosition;
  }
}

void setup() {
  Serial.begin(19200);
  pinMode(pinSW1, INPUT_PULLUP);
  pinMode(pinSW2, INPUT_PULLUP);
  pinMode(pinToggle, INPUT_PULLUP);
  pinMode(pinEncCLK, INPUT_PULLUP);
  pinMode(pinEncDT, INPUT_PULLUP);
  pinMode(pinEncSW, INPUT_PULLUP);
  digitalWrite(pinEncCLK, HIGH);
  digitalWrite(pinEncDT, HIGH);
  digitalWrite(pinEncSW, HIGH);
  attachInterrupt(digitalPinToInterrupt(pinEncCLK), tickEncoder, CHANGE);
  attachInterrupt(digitalPinToInterrupt(pinEncDT), tickEncoder, CHANGE);

  centerX = fixedCenterX;
  centerY = fixedCenterY;
  encoder.setPosition(0);
  lastEncoderPosition = encoder.getPosition();

  Serial.print("Center X: ");
  Serial.print(centerX);
  Serial.print(" | Center Y: ");
  Serial.print(centerY);
  Serial.print(" | Center X2: ");
  Serial.print(fixedCenterX2);
  Serial.print(" | Center Y2: ");
  Serial.println(fixedCenterY2);
}

void loop() {
  readEncoder();

  int rawX = readAverage(pinX, loopSamples);
  int rawY = readAverage(pinY, loopSamples);
  int rawX2 = readAverage(pinX2, loopSamples);
  int rawY2 = readAverage(pinY2, loopSamples);
  int xVal = normalizeAxis(rawX, fixedCenterX, fixedMinX, fixedMaxX);
  int yVal = normalizeAxis(rawY, fixedCenterY, fixedMinY, fixedMaxY);
  int x2Val = normalizeAxis(rawX2, fixedCenterX2, fixedMinX2, fixedMaxX2);
  int y2Val = normalizeAxis(rawY2, fixedCenterY2, fixedMinY2, fixedMaxY2);
  updateIncrementalThrottle(yVal);
  int sw1Val = digitalRead(pinSW1);
  int sw2Val = digitalRead(pinSW2);
  int toggleVal = digitalRead(pinToggle);
  int encSwVal = digitalRead(pinEncSW);
  int throttleLeftVal = (toggleVal == 0 && xVal < 0) ? 0 : 1;
  int throttleRightVal = (toggleVal == 0 && xVal > 0) ? 0 : 1;

  unsigned long nowMs = millis();
  if (nowMs - lastSerialPrintMs < serialPrintIntervalMs) {
    return;
  }
  lastSerialPrintMs = nowMs;
  int encDeltaToSend = encoderDelta;
  encoderDelta = 0;

  Serial.print("TY: ");
  Serial.print(yVal);
  Serial.print(" | TX: ");
  Serial.print(xVal);
  Serial.print(" | THROTTLE: ");
  Serial.print(throttleValue);
  Serial.print(" | X2: ");
  Serial.print(x2Val);
  Serial.print(" | Y2: ");
  Serial.print(y2Val);
  Serial.print(" | MODE2: ANALOG");
  Serial.print(" | SW1: ");
  Serial.print(sw1Val); // 0: pressed, 1: released
  Serial.print(" | SW2: ");
  Serial.print(sw2Val); // 0: pressed, 1: released
  Serial.print(" | TOGGLE: ");
  Serial.print(toggleVal); // 0: on/closed, 1: off/open
  Serial.print(" | TLEFT: ");
  Serial.print(throttleLeftVal); // 0: active, 1: inactive
  Serial.print(" | TRIGHT: ");
  Serial.print(throttleRightVal); // 0: active, 1: inactive
  Serial.print(" | ENC: ");
  Serial.print(encDeltaToSend);
  Serial.print(" | ENCSW: ");
  Serial.println(encSwVal); // 0: pressed, 1: released
}

void tickEncoder() {
  encoder.tick();
}
