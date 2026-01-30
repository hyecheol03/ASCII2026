#include <SoftwareSerial.h>

SoftwareSerial BTSerial(10, 11);

// 핀 번호 설정 (D6 고장으로 인한 변경 사항 유지)
const int touchPin = 5;      // 터치 센서 (SIG) -> D5
const int pirPin = 4;        // PIR 센서
const int buttonPin = 7;     // 복약 버튼
const int buzzerPin = 8;     // 부저
const int pirLedPin = 3;     // PIR LED
const int touchLedPin = 12;  // 터치 LED -> D12
const int alarmLedPin = 13;  // 복약 알림 LED

// 시간 설정 변수
const unsigned long LED_DURATION = 3000;    // LED 3초
const unsigned long SIGNAL_COOLDOWN = 2000; // 쿨타임 2초

// 터치 상태 변수
unsigned long lastTouchTime = 0; 
bool isTouchLedOn = false;       

// PIR 타이머 관련
bool pirLedActive = false;
bool pirIsResting = false;
unsigned long pirEventMillis = 0;
const unsigned long PIR_COOLDOWN = 10000; 

// 위급상황 및 알람 관련
unsigned long lastDoorMoveMillis = 0;
const unsigned long OVERSTAY_TIME = 1800000;   // 30분
const unsigned long INACTIVITY_TIME = 43200000; // 12시간
bool emergencySent = false;
bool alarmActive = false;
unsigned long prevAlarmMillis = 0;
int alarmCycle = 0;

void setup() {
  pinMode(touchPin, INPUT); 
  pinMode(buzzerPin, OUTPUT);
  pinMode(alarmLedPin, OUTPUT);
  pinMode(pirLedPin, OUTPUT);
  pinMode(touchLedPin, OUTPUT); 
  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(pirPin, INPUT);

  BTSerial.begin(9600);
  Serial.begin(9600);
  
  Serial.println("시스템 시작: 알람 시에만 버튼 작동");
  lastDoorMoveMillis = millis();
}

void loop() {
  unsigned long currentMillis = millis();

  // --- [파트 1: 터치 센서 로직] ---
  int touchState = digitalRead(touchPin); 

  if (touchState == HIGH && (currentMillis - lastTouchTime >= SIGNAL_COOLDOWN)) {
    lastDoorMoveMillis = currentMillis; 
    emergencySent = false;              

    BTSerial.println("DOOR_MOVED");     
    digitalWrite(touchLedPin, HIGH);    
    
    lastTouchTime = currentMillis;      
    isTouchLedOn = true;
    Serial.println(">>> 문 터치됨!");
  }

  if (isTouchLedOn && (currentMillis - lastTouchTime >= LED_DURATION)) {
    digitalWrite(touchLedPin, LOW);
    isTouchLedOn = false;
  }

  // --- [파트 2: 위급 상황 판별] ---
  if (!emergencySent) {
    if (currentMillis - lastDoorMoveMillis > INACTIVITY_TIME) {
      BTSerial.println("EMERGENCY_INACTIVITY");
      emergencySent = true;
    }
    else if (currentMillis - lastDoorMoveMillis > OVERSTAY_TIME) {
      BTSerial.println("EMERGENCY_OVERSTAY");
      emergencySent = true;
    }
  }

  // --- [파트 3: PIR 인체감지 로직] ---
  int pirVal = digitalRead(pirPin);
  if (pirVal == HIGH && !pirLedActive && !pirIsResting) {
    digitalWrite(pirLedPin, HIGH);
    pirLedActive = true;
    pirEventMillis = currentMillis;
    BTSerial.println("PIR_DETECTED");
  }
  
  if (pirLedActive && (currentMillis - pirEventMillis >= 5000)) {
    digitalWrite(pirLedPin, LOW);
    pirLedActive = false;
    pirIsResting = true;
    pirEventMillis = currentMillis;
  }
  if (pirIsResting && (currentMillis - pirEventMillis >= PIR_COOLDOWN)) {
    pirIsResting = false;
  }

  // --- [파트 4: 블루투스 알람 수신] ---
  if (BTSerial.available()) {
    char cmd = BTSerial.read();
    // 웹에서 '1'을 보내면 알람 시작
    if (cmd == '1') { 
      alarmActive = true; 
      prevAlarmMillis = currentMillis; 
      alarmCycle = 0; 
    }
    // 웹에서 '0'을 보내면 강제 종료
    else if (cmd == '0') { 
      alarmActive = false; 
      stopAlarm(); 
    }
  }

  // --- [파트 5: 알람 작동 및 버튼 확인] ---
  // ★ 조건: alarmActive가 true일 때만 이 내부 코드가 실행됨
  if (alarmActive) {
    // 1. 소리 내기 (삐- 삐- 로직)
    if (alarmCycle == 0) {
      digitalWrite(buzzerPin, HIGH);
      digitalWrite(alarmLedPin, (currentMillis / 200) % 2);
      if (currentMillis - prevAlarmMillis >= 2000) { prevAlarmMillis = currentMillis; alarmCycle = 1; }
    } else {
      digitalWrite(buzzerPin, LOW); digitalWrite(alarmLedPin, LOW);
      if (currentMillis - prevAlarmMillis >= 1000) { prevAlarmMillis = currentMillis; alarmCycle = 0; }
    }
    
    // 2. 버튼 확인 (알람이 울리는 도중에만 버튼 입력을 받음)
    if (digitalRead(buttonPin) == LOW) {
      alarmActive = false; // 알람 상태 해제
      stopAlarm();         // 소리/불 끄기
      
      // ★ 웹으로 "약 먹었어요" 신호 전송
      BTSerial.println("MEDICINE_TAKEN"); 
      Serial.println(">>> 복약 완료 버튼 눌림");
      
      delay(500); // 버튼 채터링(중복입력) 방지
    }
  }
}

void stopAlarm() { digitalWrite(buzzerPin, LOW); digitalWrite(alarmLedPin, LOW); }
