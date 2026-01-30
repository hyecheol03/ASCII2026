import streamlit as st
import random
import serial
import threading
import time
import requests  # 텔레그램 전송용 추가
from datetime import datetime
import pandas as pd
import plotly.express as px
import calendar
import plotly.graph_objects as go 

# ==========================================
# [설정] 텔레그램 및 포트
# ==========================================
TOKEN = "8385778363:AAHW3hD7JtcLJ0FVfpSc76fxKUkKYYl9-ug"
CHAT_ID = "5228127436"
SERIAL_PORT = 'COM4' 

# 문 감지 제한 시간 (초 단위)
DOOR_TIMEOUT_SEC = 10 

if 'last_alert_time' not in st.session_state:
    st.session_state.last_alert_time = ""
if 'alarm_ringing' not in st.session_state:
    st.session_state.alarm_ringing = False
    
def send_telegram_msg(text):
    """텔레그램으로 메시지를 보내는 함수 (백그라운드 실행)"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {'chat_id': CHAT_ID, 'text': text}
    try:
        requests.get(url, params=params, timeout=3)
    except: pass
# ==========================================
# 1. 디자인
# ==========================================
def apply_global_theme():
    """모든 페이지에 공통으로 적용될 테마 스타일"""
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700&display=swap');

            /* 배경 스타일 */
            [data-testid="stAppViewContainer"] {
                background-color: #f9faf9 !important;
            }

            /* 버튼 스타일 통일 */
            .stButton > button {
                background: transparent !important;
                border: 1px solid #d1dbd1 !important;
                border-radius: 40px !important;
                color: #4a634a !important;
                height: 100px !important; /* 메인 페이지와 동일한 높이 */
                transition: all 0.5s !important;
            }

            /* 버튼 내부 글자 스타일 */
            .stButton > button p, .stButton > button span {
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 24px !important; /* 가독성을 위해 살짝 키움 */
                font-weight: 400 !important;
            }

            .stButton > button:hover {
                border: 1px solid #66BB6A !important;
                background: rgba(102, 187, 106, 0.05) !important;
                letter-spacing: 2px;
            }
            
            /* 경고창 스타일도 테마에 맞춰 조정 */
            .stAlert {
                border-radius: 20px !important;
            }
                
            .main-title {
                /* 가늘고 휘날리는 느낌을 위해 얇은 명조 계열 선택 */
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 95px !important;
                font-weight: 400 !important; /* 숫자가 낮을수록 가늘어집니다 */
                color: #3e5e3e !important;
                line-height: 1 !important;
                letter-spacing: 12px !important; /* 글자 사이를 넓혀서 희날리는 느낌 강조 */
                margin-bottom: 10px !important;
                opacity: 0.85;
                
                /* 부드럽게 나타나는 애니메이션 */
                animation: flowText 2.5s ease-in-out;
            }
            .main-card {
                /* 가늘고 휘날리는 느낌을 위해 얇은 명조 계열 선택 */
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 40px !important;
                font-weight: 900 !important; /* 숫자가 낮을수록 가늘어집니다 */
                color: #3e5e3e !important;
                line-height: 1 !important;
                margin-bottom: 10px !important;
                opacity: 0.85;
                
                
            }
            /* 버튼도 얇은 선 느낌으로 변경 */
            .stButton > button {
                background: transparent !important;
                border: 1px solid #d1dbd1 !important;
                border-radius: 40px !important;
                color: #4a634a !important;
                font-weight: 400 !important;
                font-size: 22px !important;
                height: 100px !important;
                transition: all 0.5s !important;
            }
            /* 버튼 안의 '글자' 직접 타겟팅 */
            .stButton > button p, .stButton > button span {
                font-family: 'Nanum Myeongjo', serif !important;
            }
                
            /* 3. 버튼 스타일 & 폰트 강제 적용 */
            .stButton > button {
                background: transparent !important;
                border: 1px solid #d1dbd1 !important;
                border-radius: 40px !important;
                height: 120px !important;
                transition: all 0.4s !important;
            }
        </style>
    """, unsafe_allow_html=True)
# ==========================================
# 1. 시스템 설정 및 공유 DB
# ==========================================
@st.cache_resource
def get_shared_db():
    return {} 

shared_db = get_shared_db()

@st.cache_resource
def get_serial_connection(port):
    try:
        ser = serial.Serial(port, 9600, timeout=0.1)
        return ser
    except:
        return None

ser_conn = get_serial_connection(SERIAL_PORT)

def do_rerun():
    st.rerun()

# ==========================================
# 2. 세션 상태 초기화
# ==========================================
if 'mode' not in st.session_state: st.session_state.mode = "SELECT"
if 'my_pin' not in st.session_state: st.session_state.my_pin = None
if 'my_name' not in st.session_state: st.session_state.my_name = ""
if 'linked_pin' not in st.session_state: st.session_state.linked_pin = None
if 'error_msg' not in st.session_state: st.session_state.error_msg = None
if 'tmp' not in st.session_state: st.session_state.tmp = "SELECT"

# ==========================================
# 3. [신규] 문 감지 시간 모니터링 함수
# ==========================================
def door_safety_monitor(db):
    """문 감지 신호가 일정 시간 없으면 경고 발송"""
    while True:
        try:
            current_ts = time.time()
            for pin in list(db.keys()):
                user_data = db[pin]
                if user_data.get("is_out", False):
                    continue
                last_act = user_data.get("last_door_act", current_ts)
                warning_sent = user_data.get("door_warning_sent", False)
                
                if (current_ts - last_act > DOOR_TIMEOUT_SEC):
                    if not warning_sent:
                        msg = f"🚨 [위험 감지] {user_data['name']}님 댁 문이 8시간 동안 열리지 않았습니다!"
                        threading.Thread(target=send_telegram_msg, args=(msg,), daemon=True).start()
                        
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        user_data["logs"].append(f"🚨 [장기미활동] 문 미감지 경고 발생 ({timestamp})")
                        user_data["door_warning_sent"] = True
                        try: st.toast(msg, icon="🚨")
                        except: pass
        except:
            pass
        time.sleep(1)

# ==========================================
# 3-2. 백그라운드 신호 수신
# ==========================================
def serial_reader(ser, db):
    while True:
        try:
            if ser and ser.in_waiting > 0:
                raw = ser.readline()
                try: line = raw.decode('utf-8').strip()
                except: line = raw.decode('cp949', errors='ignore').strip()
                
                if line:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    today_date_str = datetime.now().strftime("%Y-%m-%d")
                    tg_msg = None
                    
                    # [추가] DB에 등록된 핀들을 순회하며 외출 상태 확인
                    active_pins = list(db.keys())
                    for pin in active_pins:
                        
                        # [핵심] 외출 중("is_out" == True)이면 신호 처리 및 로그 기록 건너뜀
                        if db[pin].get("is_out", False):
                            continue

                        if "logs" not in db[pin]: continue
                        target_logs = db[pin]["logs"]
                        
                        # --- 신호 처리 및 분류 (외출 아닐 때만 실행) ---
                        if line == "PIR_DETECTED":
                            tg_msg = "🐾 [활동 감지] 거실/침대에 움직임이 포착되었습니다."
                            if db[pin].get("today_wake_time") is None:
                                now = datetime.now()
                                wake_float = now.hour + (now.minute / 60.0)
                                db[pin]["today_wake_time"] = wake_float
                                db[pin]["logs"].append(f"☀ [기상체크] 기상 감지됨 ({timestamp})")
                        
                        elif line == "DOOR_MOVED":
                            tg_msg = "🚪 [문 감지] 화장실 문이 움직였습니다."
                            db[pin]["last_door_act"] = time.time()
                            db[pin]["door_warning_sent"] = False 

                        elif line == "MEDICINE_TAKEN":
                            tg_msg = "💊 [복약 완료] 어르신이 약을 복용하셨습니다."
                            st.session_state.alarm_ringing = False
                            if "med_history" not in db[pin]: db[pin]["med_history"] = []
                            db[pin]["med_history"].append(today_date_str)

                        elif line == "EMERGENCY_OVERSTAY":
                            tg_msg = "🚨 [긴급] 화장실 내 장시간 체류! 확인이 시급합니다."
                        elif line == "EMERGENCY_INACTIVITY":
                            tg_msg = "⚠️ [주의] 12시간 동안 활동이 전혀 없습니다."
                        
                        # 로그 텍스트 추가
                        if "PIR" in line: target_logs.append(f"🏃 [활동감지] 움직임 감지! ({timestamp})")
                        elif "DOOR" in line: target_logs.append(f"🚪 [문열림] 문 움직임 감지 ({timestamp})")
                        elif "MEDICINE" in line: target_logs.append(f"💊 [복약확인] 약 복용 완료 ({timestamp})")
                        elif "EMERGENCY" in line: target_logs.append(f"🚨 [비상] {tg_msg if tg_msg else line} ({timestamp})")
                        elif "ALARM_STARTED" in line: target_logs.append(f"🔔 [기기] 알람 작동 ({timestamp})")
                        elif "ALARM_STOPPED" in line: target_logs.append(f"🔕 [기기] 알람 중지 ({timestamp})")
                        else: 
                            if line not in ["SENSOR_READY_AGAIN", "LED_OFF_RESTING"]:
                                target_logs.append(f"📡 [신호] {line} ({timestamp})")
                    
                    # 텔레그램 전송 (외출 중이면 위에서 걸러지므로 안 보내짐)
                    if tg_msg:
                        threading.Thread(target=send_telegram_msg, args=(tg_msg,), daemon=True).start()
                        try: st.toast(tg_msg, icon="🔔") 
                        except: pass

        except: pass 
        time.sleep(0.1)

if ser_conn and 'thread_started' not in st.session_state:
    threading.Thread(target=serial_reader, args=(ser_conn, shared_db), daemon=True).start()
    threading.Thread(target=door_safety_monitor, args=(shared_db,), daemon=True).start()
    st.session_state.thread_started = True

# ==========================================
# 4. 화면 디자인 (CSS)
# ==========================================
st.markdown("""
    <style>
    @media (max-width: 600px) {
        .header-card h2 { font-size: 24px !important; }
        .cal-day-label { font-size: 14px !important; }
        .cal-date { font-size: 20px !important; margin-bottom: 4px !important; }
        .cal-cell { min-height: 70px !important; padding: 8px 2px !important; border-radius: 12px !important; gap: 2px !important; }
        .dot { width: 8px !important; height: 8px !important; }
        .dot-box { gap: 3px !important; }
        .legend-container { flex-direction: column !important; padding: 0 10px !important; }
    }
    .legend-container { display: flex; justify-content: center; gap: 10px; margin-top: 30px; }
    [data-testid="stAppViewContainer"] { background-color: #FDFBF7; }
    .main-card { background-color: white; padding: 25px; border-radius: 25px; box-shadow: 0 8px 20px rgba(0,0,0,0.05); text-align: center; margin-bottom: 20px; }
    .stButton>button { border-radius: 20px !important; height: 120px !important; font-size: 19px !important; font-weight: 800 !important; border: none !important; color: #1A1A1A !important; white-space: pre-wrap !important; }
    div[data-testid="column"]:nth-of-type(1) .stButton>button { background-color: #F07E65 !important; } 
    div[data-testid="column"]:nth-of-type(2) .stButton>button { background-color: #69B99D !important; } 
    .purple-btn .stButton>button { background-color: #9D5B8B !important; color: white !important; }
    .yellow-btn .stButton>button { background-color: #E9C46A !important; }
    
    .motion-box { background-color: #E8F5E9; padding: 12px; border-radius: 12px; border-left: 6px solid #2E7D32; margin-bottom: 8px; font-size: 14px; color: black; }
    .med-box { background-color: #FFFDE7; padding: 12px; border-radius: 12px; border-left: 6px solid #FBC02D; margin-bottom: 8px; font-size: 14px; color: black; }
    .system-box { background-color: #F5F5F5; padding: 10px; border-radius: 12px; color: #666; font-size: 13px; margin-bottom: 5px; }
    
    .header-card { padding: 30px; border-radius: 30px; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    .header-card h2 { font-size: 38px !important; font-weight: 900 !important; margin: 0; }
    .sleep-stat-container { display: flex; flex-direction: column; gap: 15px; margin-top: 25px; }
    .sleep-stat-box { background: white; padding: 25px; border-radius: 25px; border-left: 10px solid #636EFA; box-shadow: 0 5px 15px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; }
    .sleep-stat-lbl { font-size: 24px; font-weight: 800; color: #444; }
    .sleep-stat-val { font-size: 36px; font-weight: 900; color: #636EFA; }
    .calendar-container { background: white; padding: 15px; border-radius: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
    .cal-day-label { font-weight: 900; font-size: 22px; text-align: center; }
    .cal-cell { padding: 15px 2px; border-radius: 20px; background: #F9F9FB; min-height: 100px; border: 1px solid #E0E0E0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .cal-cell.today { border: 4px solid #6c5ce7; background: #EFEDFF; }
    .cal-date { font-weight: 900; font-size: 32px; color: #000; margin-bottom: 8px; }
    .dot-box { display: flex; justify-content: center; gap: 6px; }
    .dot { width: 14px; height: 14px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.1); }
    .dot.done { background-color: #00C897 !important; } 
    .dot.miss { background-color: #FF4D4D !important; } 
    .dot.none { background-color: #D1D1D1 !important; }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 5. 로직 함수
# ==========================================
def set_mode(mode, sub): 
    st.session_state.tmp = sub
    st.session_state.mode = mode

def return_home():
    st.session_state.mode = "SELECT"
    st.session_state.linked_pin = None
    st.session_state.error_msg = None

def register_elderly():
    name = st.session_state.get("input_name")
    if name:
        pin = str(random.randint(1000, 9999))
        shared_db[pin] = {
            "name": name, 
            "logs": ["(시스템) 기기 연결 대기 중..."],
            "alarms": [],
            "med_history": [],
            "last_door_act": time.time(),
            "door_warning_sent": False,
            "today_wake_time": None,  # [추가] 오늘의 기상 시간 초기화
            "is_out": False  # [추가] 외출 상태 저장용 (기본: 재실)
        }
        st.session_state.my_pin = pin
        st.session_state.my_name = name
        st.session_state.mode = "ELDERLY_DASHBOARD"
        threading.Thread(target=send_telegram_msg, args=(f"👵 {name}님이 시스템에 접속하셨습니다.",), daemon=True).start()

def attempt_link():
    name, pin = st.session_state.get("link_name"), st.session_state.get("link_pin")
    if pin in shared_db and shared_db[pin]["name"] == name:
        st.session_state.linked_pin = pin
        st.session_state.error_msg = None
        st.session_state.mode = "PROTECTOR_DASHBOARD"
    else: 
        st.session_state.error_msg = "일치하는 정보가 없습니다."

def send_alarm(val):
    # [추가] 외출 중이면 보호자 알람 전송 차단
    if shared_db[pin].get("is_out", False):
        st.toast("⚠️ 어르신이 외출 중이라 알람을 보낼 수 없습니다.", icon="🚫")
        return
    if ser_conn:
        ser_conn.write(val.encode())
        pin = st.session_state.linked_pin
        shared_db[pin]["logs"].append(f"📢 [보호자] 알람 {'작동' if val=='1' else '중지'} 명령 전송")
        threading.Thread(target=send_telegram_msg, args=(f"📢 [보호자] 원격 알람 {'작동' if val=='1' else '중지'}",), daemon=True).start()

def global_alarm_check():
    now_str = datetime.now().strftime("%H:%M")
    target_pin = st.session_state.my_pin or st.session_state.linked_pin
    
    if target_pin and target_pin in shared_db:
        # [추가] 외출 중이면 자동 알람 체크 건너뜀
        if shared_db[target_pin].get("is_out", False):
            return
        name = shared_db[target_pin]["name"]
        alarms = shared_db[target_pin].get("alarms", [])
        
        if now_str in alarms and st.session_state.last_alert_time != now_str:
            st.session_state.last_alert_time = now_str
            st.session_state.alarm_ringing = True 
            
            if ser_conn:
                try:
                    ser_conn.write(b'1')
                    shared_db[target_pin]["logs"].append(f"⏰ [시스템] 예약 알람 작동 ({now_str})")
                except: pass
            
            threading.Thread(target=send_telegram_msg, args=(f"📢 [{name}님] 약 드실 시간이에요! ({now_str})",), daemon=True).start()
            st.toast(f"📢 {name}님이 약 드실 시간이에요!", icon="🔔")
            st.error(f"📢 **약 드실 시간입니다! ({now_str})**")

# ==========================================
# 6. 메인 실행 라우터
# ==========================================
global_alarm_check()

if st.session_state.mode == "SELECT":
    # 폰트 소스: 나눔명조(가늘게) 및 나눔손글씨 펜 스타일
    font_fix_style = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Nanum+Pen+Script&display=swap');

            .main-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                padding-top: 80px;
                padding-bottom: 50px;
            }

            h1 {
                font-family: 'Nanum Myeongjo', serif !important;
            }
            h3 {
                font-family: 'Nanum Myeongjo', serif !important;
            }
            .main-title {
                /* 가늘고 휘날리는 느낌을 위해 얇은 명조 계열 선택 */
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 95px !important;
                font-weight: 400 !important; /* 숫자가 낮을수록 가늘어집니다 */
                color: #3e5e3e !important;
                line-height: 1 !important;
                letter-spacing: 12px !important; /* 글자 사이를 넓혀서 희날리는 느낌 강조 */
                margin-bottom: 10px !important;
                opacity: 0.85;
                
                /* 부드럽게 나타나는 애니메이션 */
                animation: flowText 2.5s ease-in-out;
            }

            .main-subtitle {
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 12px !important;
                color: #8db58d !important;
                font-weight: 400 !important;
                letter-spacing: 10px !important;
                text-indent: 10px;
                margin-top: 10px !important;
                margin-bottom: 60px !important;
            }

            @keyframes flowText {
                0% { opacity: 0; letter-spacing: 30px; filter: blur(5px); }
                100% { opacity: 0.85; letter-spacing: 12px; filter: blur(0px); }
            }

            /* 전체 배경을 조금 더 차분한 톤으로 */
            [data-testid="stAppViewContainer"] {
                background-color: #f9faf9 !important;
            }

            /* 3. 버튼 스타일 & 폰트 강제 적용 */
            .stButton > button {
                background: transparent !important;
                border: 1px solid #d1dbd1 !important;
                border-radius: 40px !important;
                height: 120px !important;
                transition: all 0.4s !important;
            }

            /* 버튼 안의 '글자' 직접 타겟팅 */
            .stButton > button p, .stButton > button span {
                font-family: 'Nanum Myeongjo', serif !important;
            }

            /* 버튼도 얇은 선 느낌으로 변경 */
            .stButton > button {
                background: transparent !important;
                border: 1px solid #d1dbd1 !important;
                border-radius: 40px !important;
                color: #4a634a !important;
                font-weight: 400 !important;
                font-size: 22px !important;
                height: 60px;
                transition: all 0.5s !important;
            }
            
            .stButton > button:hover {
                border: 1px solid #66BB6A !important;
                background: rgba(102, 187, 106, 0.05) !important;
                letter-spacing: 2px;
            }
        </style>

        <div class="main-container">
            <div class="main-title">늘곁에</div>
            <div class="main-subtitle">AI SMART CARE</div>
        </div>
    """
    st.markdown(font_fix_style, unsafe_allow_html=True)
    if not ser_conn: st.warning("🔌 아두이노 연결을 확인해주세요.")
    st.button("어르신 시작", on_click=set_mode, args=("ELDERLY_LOGIN", st.session_state.mode), use_container_width=True)
    st.button("보호자 시작", on_click=set_mode, args=("PROTECTOR", st.session_state.mode), use_container_width=True)

elif st.session_state.mode == "ELDERLY_LOGIN":
    apply_global_theme()  # 1. 공통 테마 적용
    st.markdown('<div class="main-card">어르신 등록</div>', unsafe_allow_html=True)
    st.text_input("성함을 입력해주세요", key="input_name")
    st.button("입장하기", on_click=register_elderly, use_container_width=True)
    st.button("뒤로가기", on_click=return_home, use_container_width=True)

elif st.session_state.mode == "ELDERLY_DASHBOARD":
    apply_global_theme()  # 1. 공통 테마 적용
    pin, name = st.session_state.my_pin, st.session_state.my_name
    st.markdown(f"### 👵 {name}님, 안녕하세요!")
    st.success(f"보호자 연동용 PIN: **{pin}**")
    
    st.write("---")
    c1, c2 = st.columns(2)
    is_out = shared_db[pin].get("is_out", False) # 현재 외출 상태 확인
    with c1: 
        st.button("🌙\n수면패턴", on_click=set_mode, args=("SLEEP_PATTERN", st.session_state.mode),use_container_width=True)
        # 버튼 텍스트 및 스타일 결정
        btn_text = "🚫\n외출중" if is_out else "🏠\n외출"
        btn_class = "out-mode-btn" if is_out else "in-mode-btn"
        
        # div로 감싸서 클래스 적용
        st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
        if st.button(btn_text, key="toggle_out", use_container_width=True):
            shared_db[pin]["is_out"] = not is_out # 상태 토글 (True <-> False)
            # 상태 변경 시 로그 남기기
            status_msg = "외출을 시작합니다." if not is_out else "귀가하셨습니다."
            shared_db[pin]["logs"].append(f"🏃 {status_msg} ({datetime.now().strftime('%H:%M:%S')})")
            st.rerun() # 화면 새로고침
        st.markdown('</div>', unsafe_allow_html=True)
    with c2: 
        st.button("💊\n복약패턴", on_click=set_mode, args=("MED_PATTERN", st.session_state.mode),use_container_width=True)
        st.markdown('<div class="yellow-btn">', unsafe_allow_html=True)
        st.button("⚙️\n설정", on_click=set_mode, args=("SETTINGS", st.session_state.mode),use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.subheader("📋 실시간 상태")
    logs = shared_db[pin]["logs"]
    for log in reversed(logs[-5:]):
        if "[활동감지]" in log: st.markdown(f"<div class='motion-box'>{log}</div>", unsafe_allow_html=True)
        elif "[복약확인]" in log: st.markdown(f"<div class='med-box'>{log}</div>", unsafe_allow_html=True)
        elif "[비상]" in log: st.markdown(f"<div class='system-box' style='color:red;'>{log}</div>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='system-box'>{log}</div>", unsafe_allow_html=True)
    
    if st.button("↩️ 로그아웃"): return_home()
    time.sleep(1)
    do_rerun()
elif st.session_state.mode == "SLEEP_PATTERN":
    apply_global_theme()  # 1. 공통 테마 적용
    
    st.markdown("""
        <style>
            .header-card-sleep {
                background: linear-gradient(135deg, #a8e6cf 0%, #dcedc1 100%);
                padding: 30px; border-radius: 30px; text-align: center; margin-bottom: 25px;
            }
            .header-card-sleep h2 { color: #3e5e3e !important; font-family: 'Nanum Myeongjo', serif !important; }
            .sleep-stat-box {
                background: white; padding: 25px; border-radius: 25px;
                border-left: 10px solid #8db58d; box-shadow: 0 5px 15px rgba(0,0,0,0.05);
                display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;
            }
            .sleep-stat-lbl { font-size: 20px; font-weight: 700; color: #444; }
            .sleep-stat-val { font-size: 28px; font-weight: 900; color: #3e5e3e; }
        </style>
        <div class="header-card-sleep">
            <h2>🌙 수면 분석 리포트</h2>
        </div>
    """, unsafe_allow_html=True)
    
    # [수정] 고정 시드값으로 일~금(6일치) 데이터 생성
    random.seed(42) # 고정 시드 설정
    days = ["일", "월", "화", "수", "목", "금", "토"]
    wake_hours = []
    
    # 일~금요일(6일) 데이터 생성 (6시~8시 사이 랜덤)
    for _ in range(6):
        rand_time = 6.0 + random.random() * 2.0 
        wake_hours.append(round(rand_time, 1))
    
    # [수정] 실제 오늘(토요일) PIR 신호가 있다면 리스트에 추가
    pin = st.session_state.my_pin or st.session_state.linked_pin
    if pin and pin in shared_db:
        today_wake = shared_db[pin].get("today_wake_time")
        if today_wake:
            wake_hours.append(today_wake)
            
    fig = go.Figure(go.Scatter(
        x=days[:len(wake_hours)], # 데이터 개수만큼 X축 설정
        y=wake_hours, mode='lines+markers+text',
        text=[f"{int(h):02d}:{int((h%1)*60):02d}" for h in wake_hours],
        textposition="top center",
        textfont=dict(size=14, color="#3e5e3e", family="Nanum Myeongjo"),
        line=dict(width=6, color='#8db58d', shape='spline'),
        marker=dict(size=15, color='white', line=dict(width=3, color='#8db58d')),
        fill='tozeroy', fillcolor='rgba(141, 181, 141, 0.1)'
    ))
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        height=350, margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(tickfont=dict(size=18, color="#555"), showgrid=False),
        yaxis=dict(
            range=[5, 10], # 5시부터 10시까지 표시
            tickvals=[6, 7, 8, 9],
            ticktext=["6시", "7시", "8시", "9시"],
            tickfont=dict(size=16), showgrid=True, gridcolor='#EEEEEE'
        )
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    # 평균 계산
    avg_wake = sum(wake_hours) / len(wake_hours)
    
    st.markdown(f"""
        <div class="sleep-stat-container">
            <div class="sleep-stat-box">
                <span class="sleep-stat-lbl">평균 기상 시간</span>
                <span class="sleep-stat-val">{int(avg_wake):02d}시 {int((avg_wake%1)*60):02d}분</span>
            </div>
            <div class="sleep-stat-box" style="border-left-color: #00C897;">
                <span class="sleep-stat-lbl">오늘 기상</span>
                <span class="sleep-stat-val">{"측정 중..." if len(wake_hours) < 7 else f"{int(wake_hours[-1]):02d}시 {int((wake_hours[-1]%1)*60):02d}분"}</span>
            </div>
            
        </div>
    """, unsafe_allow_html=True)
    st.write(" ")
    st.button("뒤로가기", on_click=set_mode, args=(st.session_state.tmp , st.session_state.mode), use_container_width=True)
    
    time.sleep(1)
    do_rerun()

elif st.session_state.mode == "MED_PATTERN":
    # 1. 공통 테마 및 잉크립퀴드/나눔명조 적용
    st.markdown("""
        <style>
            @font-face {
                font-family: 'InkLiquid';
                src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/InkLipquid.woff') format('woff');
            }
            @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700&display=swap');

            /* 전체 배경색 */
            [data-testid="stAppViewContainer"] {
                background-color: #f9faf9 !important;
            }

            /* 상단 헤더 카드 (사진 디자인 반영) */
            .header-card-custom {
                background: linear-gradient(to right, #b2e2b2, #d9f2d9); /* 연녹색 그라데이션 */
                padding: 30px;
                border-radius: 25px;
                text-align: center;
                margin-bottom: 30px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }
            .header-title {
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 38px !important;
                color: #2e7d32 !important;
                margin: 0;
            }

            /* 달력 날짜 폰트 */
            .cal-date {
                font-family: 'Pretendard', sans-serif;
                font-weight: 600;
            }
            
            /* 현재 월 표시 (잉크립퀴드) */
            .month-display {
                font-family: 'InkLiquid' !important;
                font-size: 55px !important;
                color: #3e5e3e;
                text-align: center;
                margin: 20px 0;
            }

            /* 하단 요약 카드 (사진의 평균 기상 시간 스타일) */
            .info-card {
                background: white;
                padding: 20px 30px;
                border-radius: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03);
                border-left: 8px solid #66bb6a;
            }
            .info-label {
                font-family: 'Nanum Myeongjo', serif;
                font-size: 20px;
                color: #555;
            }
            .info-value {
                font-family: 'Nanum Myeongjo', serif;
                font-size: 24px;
                font-weight: 900;
                color: #2e7d32;
            }

            /* 점(Dot) 스타일 수정 */
            .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin: 0 2px; }
            .dot.done { background-color: #66bb6a; } /* 먹었음 - 녹색 */
            .dot.miss { background-color: #ff8a65; } /* 안먹었음 - 주황/노랑 계열 */
            .dot.none { background-color: #eeeeee; }
        </style>
    """, unsafe_allow_html=True)

    # 상단 헤더 (사진 디자인)
    st.markdown("""
        <div class="header-card-custom">
            <h2 class="header-title">복약 분석 리포트</h2>
        </div>
    """, unsafe_allow_html=True)

    now = datetime.now()
    cal = calendar.monthcalendar(now.year, now.month)
    
    # 월 표시 (잉크립퀴드 폰트)
    st.markdown(f'<div class="month-display">{now.year}년 {now.month}월</div>', unsafe_allow_html=True)
    
    pin = st.session_state.my_pin
    med_history = shared_db[pin].get("med_history", []) 
    
    # --- 달력 로직은 기존 유지하되 스타일 클래스 적용 ---
    html_cal = '<div class="calendar-container" style="background:white; padding:20px; border-radius:25px; box-shadow:0 4px 15px rgba(0,0,0,0.03);"><div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px;">'
    for day_label in ["일", "월", "화", "수", "목", "금", "토"]:
        color = "#FF8A65" if day_label == "일" else ("#4D7CFF" if day_label == "토" else "#1A1A1A")
        html_cal += f'<div style="text-align:center; font-weight:900; color:{color}; padding-bottom:10px;">{day_label}</div>'
    
    today_val = now.day
    for week in cal:
        for day in week:
            if day == 0: html_cal += '<div></div>'
            else:
                is_today = "border: 2px solid #66bb6a;" if day == today_val else ""
                current_date_str = f"{now.year}-{now.month:02d}-{day:02d}"
                dots = ""
                
                if day < today_val:
                    random.seed(now.year * 10000 + now.month * 100 + day)
                    for _ in range(3):
                        status = random.choice(["done", "done", "miss"])
                        dots += f'<div class="dot {status}"></div>'
                elif day == today_val:
                    taken_count = med_history.count(current_date_str)
                    for i in range(3):
                        dots += f'<div class="dot {"done" if i < taken_count else "none"}"></div>'
                else: 
                    dots = '<div class="dot none"></div><div class="dot none"></div><div class="dot none"></div>'
                
                html_cal += f'<div style="text-align:center; padding:10px; border-radius:15px; {is_today}"><div class="cal-date" style="font-size:18px; margin-bottom:5px;">{day}</div><div>{dots}</div></div>'
    html_cal += '</div></div>'
    st.markdown(html_cal, unsafe_allow_html=True)

    # 하단 정보 카드 (사진의 평균 기상 시간 스타일)
    taken_this_month = 42 # 예시 데이터
    st.markdown(f"""
        <div style="margin-top:30px;">
            <div class="info-card">
                <span class="info-label">이달의 복약 준수율</span>
                <span class="info-value">85%</span>
            </div>
            <div class="info-card" style="border-left-color: #ffb74d;">
                <span class="info-label">오늘의 복약 상태</span>
                <span class="info-value">진행 중...</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.write(" ")
    st.button("↩️ 뒤로가기", on_click=set_mode, args=(st.session_state.tmp , st.session_state.mode), use_container_width=True)
    
    time.sleep(1)
    st.rerun()

elif st.session_state.mode == "PROTECTOR":
    apply_global_theme()  # 1. 공통 테마 적용
    st.markdown('<div class="main-card">보호자 연동</div>', unsafe_allow_html=True)
    st.text_input("어르신 성함", key="link_name")
    st.text_input("PIN 번호", key="link_pin", max_chars=4)
    if st.session_state.error_msg: st.error(st.session_state.error_msg)
    st.button("연동하기", on_click=attempt_link, use_container_width=True)
    st.button("뒤로가기", on_click=return_home, use_container_width=True)
    
elif st.session_state.mode == "PROTECTOR_DASHBOARD":
    apply_global_theme()  # 1. 공통 테마 적용
    st.session_state.my_pin = linked_pin = st.session_state.linked_pin
    name = shared_db[linked_pin]["name"]
    st.markdown(f"### 👨‍⚕️ {name} 보호자 님, 안녕하세요!")
    current_time = datetime.now().strftime("%H:%M")
    
    st.write("---")
    c1, c2 = st.columns(2)
    with c1: 
        st.button("🌙\n수면패턴", on_click=set_mode, args=("SLEEP_PATTERN", st.session_state.mode,),use_container_width=True)
        st.markdown('<div class="purple-btn">', unsafe_allow_html=True)
        st.button("로그 보기", on_click=set_mode, args=('LOG_CHECK', st.session_state.mode), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2: 
        st.button("💊\n복약패턴", on_click=set_mode, args=("MED_PATTERN", st.session_state.mode),use_container_width=True)
        st.markdown('<div class="yellow-btn">', unsafe_allow_html=True)
        st.button("⚙️\n설정", on_click=set_mode, args=("SETTINGS", st.session_state.mode),use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    time.sleep(1)
    do_rerun()
elif st.session_state.mode == "LOG_CHECK":
    apply_global_theme()  # 1. 공통 테마 적용
    tab1, tab2 = st.tabs(["💊 복약/알람 현황", "🏃 실시간 활동"])
    linked_pin = st.session_state.linked_pin
    logs = shared_db[linked_pin]["logs"]
    st.button("↩️ 뒤로가기", on_click=set_mode, args=("PROTECTOR_DASHBOARD", st.session_state.mode), use_container_width=True)
    with tab1:
        for log in reversed(logs):
            if "[복약확인]" in log or "[보호자]" in log or "알람" in log: st.markdown(f"<div class='med-box'>{log}</div>", unsafe_allow_html=True)
    with tab2:
        for log in reversed(logs):
            if "[활동감지]" in log or "[비상]" in log or "[문열림]" in log: st.markdown(f"<div class='motion-box'>{log}</div>", unsafe_allow_html=True)

elif st.session_state.mode == "SETTINGS":
    # 1. 공통 테마 및 폰트 설정
    st.markdown("""
        <style>
            @font-face {
                font-family: 'InkLiquid';
                src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/InkLipquid.woff') format('woff');
            }
            @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&display=swap');

            /* 상단 헤더 카드 (빨강-주황 그라데이션) */
            .header-card-red {
                background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%); /* 부드러운 분홍-주황 */
                background-image: linear-gradient(135deg, #ff6b6b 0%, #ffad60 100%); /* 요청하신 빨강-주황 */
                padding: 35px 25px;
                border-radius: 25px;
                text-align: center;
                margin-bottom: 30px;
                box-shadow: 0 10px 20px rgba(255, 107, 107, 0.15);
            }
            
            .header-title-main {
                font-family: 'Nanum Myeongjo', serif !important;
                font-size: 38px !important;
                color: white !important;
                margin: 0;
                font-weight: 800;
            }

            /* 서브텍스트 (잉크립퀴드) */
            .header-subtitle {
                font-family: 'InkLiquid' !important;
                font-size: 24px !important;
                color: rgba(255, 255, 255, 0.9) !important;
                margin-top: 10px;
            }

            /* 등록된 알람 리스트 카드 (사진 디자인 반영) */
            .alarm-card {
                background: white;
                padding: 20px 25px;
                border-radius: 20px;
                display: flex;
                align-items: center;
                margin-bottom: 15px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03);
                border-left: 8px solid #ff6b6b; /* 빨간색 포인트 선 */
            }

            .alarm-time-text {
                font-family: 'Nanum Myeongjo', serif;
                font-size: 32px;
                font-weight: 900;
                color: #333;
                margin-left: 15px;
            }

            /* 섹션 타이틀 */
            .section-title {
                font-family: 'Nanum Myeongjo', serif;
                font-size: 22px;
                color: #444;
                margin: 20px 0 15px 5px;
                font-weight: 700;
            }
            
            /* Expander 스타일 조정 */
            .stExpander {
                border-radius: 20px !important;
                border: 1px solid #ff6b6b33 !important;
                background-color: white !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # 상단 헤더
    st.markdown("""
        <div class="header-card-red">
            <h2 class="header-title-main">⏰ 알람 관리</h2>
            <div class="header-subtitle">약 드실 시간을 정해두면 제가 알려드릴게요</div>
        </div>
    """, unsafe_allow_html=True)

    pin = st.session_state.my_pin
    if "alarms" not in shared_db[pin]: shared_db[pin]["alarms"] = []

    # ➕ 알람 추가 섹션
    with st.expander("➕ 새로운 복약 시간 등록하기", expanded=True):
        c1, c2 = st.columns(2)
        with c1: new_h = st.selectbox("시", range(24), format_func=lambda x: f"{x:02d}시")
        with c2: new_m = st.selectbox("분", range(60), format_func=lambda x: f"{x:02d}분")
        
        if st.button("🔔 이 시간에 알람 추가", use_container_width=True):
            new_time = f"{new_h:02d}:{new_m:02d}"
            if new_time not in shared_db[pin]["alarms"]:
                shared_db[pin]["alarms"].append(new_time)
                shared_db[pin]["alarms"].sort() 
                st.rerun()
            else:
                st.warning("이미 등록된 시간입니다.")

    st.markdown('<div class="section-title">📋 현재 등록된 시간 목록</div>', unsafe_allow_html=True)
    
    if not shared_db[pin]["alarms"]:
        st.info("등록된 알람이 없습니다. 위에서 시간을 추가해주세요!")
    else:
        for idx, alarm in enumerate(shared_db[pin]["alarms"]):
            col_time, col_del = st.columns([3, 1], vertical_alignment="center")
            
            with col_time:
                st.markdown(f"""
                    <div class="alarm-card">
                        <span style="font-size: 28px;">🔔</span>
                        <span class="alarm-time-text">{alarm}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            with col_del:
                # 삭제 버튼은 테마에 맞게 빨간색 톤 유지
                if st.button("🗑️ 삭제", key=f"del_{idx}", use_container_width=True):
                    shared_db[pin]["alarms"].pop(idx)
                    st.rerun()

    st.write(" ")
    st.write("---")
    st.button("↩️ 대시보드로 돌아가기", on_click=set_mode, args=(st.session_state.tmp , st.session_state.mode), use_container_width=True)
