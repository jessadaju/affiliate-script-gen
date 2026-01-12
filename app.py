import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image
import datetime
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script & Sora Gen", page_icon="🎥", layout="centered")

# --- 2. ระบบฐานข้อมูล (Google Sheets) ---
SHEET_NAME = "user_db" # ⚠️ ตรวจสอบว่าชื่อไฟล์ Google Sheet ของคุณชื่อนี้เป๊ะๆ

def connect_to_gsheet():
    """เชื่อมต่อ Google Sheets โดยอ่านจาก Secrets"""
    try:
        # อ่านค่าจาก Secrets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # ตรวจสอบว่ามี Secrets หรือไม่
        if "gcp_service_account" not in st.secrets:
            st.error("❌ ไม่พบข้อมูล Secrets กรุณาตั้งค่าใน Streamlit Cloud")
            return None

        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        st.info("💡 คำแนะนำ: อย่าลืมกด Share ไฟล์ Google Sheet ให้กับอีเมลใน Secrets ด้วยนะครับ")
        return None

def register_user(username, password, email):
    """สมัครสมาชิกแบบบันทึกลง Sheet"""
    sheet = connect_to_gsheet()
    if not sheet: return False

    try:
        # เช็กว่ามี Username ซ้ำไหม
        existing_users = sheet.col_values(1) # คอลัมน์ 1 คือ Username
        if username in existing_users:
            return False # ชื่อซ้ำ
        
        # บันทึกข้อมูลใหม่
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # เพิ่มแถวใหม่ต่อท้าย (Append)
        sheet.append_row([username, hashed_pw, email, today])
        return True
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")
        return False

def login_user(username, password):
    """ล็อกอินโดยดึงข้อมูลจาก Sheet"""
    sheet = connect_to_gsheet()
    if not sheet: return None

    try:
        # ค้นหา Username
        try:
            cell = sheet.find(username) # หาว่า Username อยู่แถวไหน
        except gspread.exceptions.CellNotFound:
            return None # หาไม่เจอ

        if cell:
            row_data = sheet.row_values(cell.row)
            # โครงสร้าง: [username, password_hash, email, start_date]
            
            # เช็ก Password
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            if row_data[1] == hashed_pw:
                return row_data # ส่งข้อมูลกลับไป
        return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

def check_trial(start_date_str):
    """คำนวณวันทดลองใช้"""
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        now = datetime.datetime.now()
        diff = (now - start_date).days
        return diff, 3 - diff
    except:
        return 0, 3

# --- 3. ฟังก์ชัน AI ---
def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        preferred = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        try:
            avail = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except: return preferred[0]
        for m in preferred:
            if m in avail: return m
        return avail[0] if avail else preferred[0]
    except: return None

def scrape_web(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        res = scraper.get(url, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'html.parser')
            title, desc = "", ""
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if '@type' in data and data['@type'] == 'Product':
                        title = data.get('name', '')
                        desc = data.get('description', '')
                        break
                except: continue
            if not title and soup.title: title = soup.title.string
            return title, desc
        return None, "Error"
    except: return None, "Error"

def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    prompt_text = f"Role: Sora AI & Ad Expert. Task: Script for '{product}'. Lang: THAI. Info: {features} {url_info} Tone: {tone}"
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
        except: pass
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    return model.generate_content(contents).text

# --- 4. User Interface ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

def login_screen():
    st.markdown("""
    <style>
        .main-card {background-color: #262730; padding: 2rem; border-radius: 10px; text-align: center; margin-bottom: 20px;}
        h1 {color: #FF4B4B;}
    </style>
    <div class="main-card">
        <h1>💎 Affiliate Gen Pro (Business)</h1>
        <p>ระบบสมาชิกถาวร + ทดลองฟรี 3 วัน</p>
    </div>
    """, unsafe_allow_html=True)

    # เช็กการเชื่อมต่อก่อนเลย เพื่อความชัวร์
    if st.button("🛠️ ทดสอบการเชื่อมต่อ Google Sheets"):
        sheet = connect_to_gsheet()
        if sheet:
            st.success(f"✅ เชื่อมต่อสำเร็จ! เจอไฟล์: {sheet.title}")
        else:
            st.error("❌ เชื่อมต่อไม่ได้ กรุณาเช็ก Secrets และการ Share ไฟล์")

    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])

    with tab1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("เข้าสู่ระบบ", use_container_width=True):
                with st.spinner("กำลังตรวจสอบ..."):
                    data = login_user(u, p)
                    if data:
                        used, left = check_trial(data[3])
                        if used > 3:
                            st.error(f"หมดเวลาทดลองใช้ ({used} วัน) กรุณาต่ออายุ")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.user_info = {"name": data[0], "email": data[2], "left": left}
                            st.rerun()
                    else:
                        st.error("ไม่พบผู้ใช้ หรือ รหัสผิด (หรือยังไม่ได้สมัคร)")

    with tab2:
        with st.form("reg"):
            new_u = st.text_input("Username *")
            new_e = st.text_input("Email *")
            new_p = st.text_input("Password *", type="password")
            if st.form_submit_button("สมัครสมาชิก", use_container_width=True):
                if new_u and new_e and new_p:
                    with st.spinner("กำลังบันทึกลง Google Sheets..."):
                        if register_user(new_u, new_p, new_e):
                            st.success("✅ สมัครสำเร็จ! ข้อมูลถูกบันทึกลงระบบแล้ว")
                            st.info("กรุณากลับไปหน้า 'เข้าสู่ระบบ' เพื่อใช้งาน")
                        else:
                            st.warning("สมัครไม่สำเร็จ (ชื่ออาจซ้ำ หรือเชื่อมต่อไม่ได้)")
                else:
                    st.warning("กรอกให้ครบนะ")

def main_app():
    info = st.session_state.user_info
    st.info(f"👤 {info['name']} ({info['email']}) | ⏳ เหลือ {info['left']} วัน")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
        
    my_api_key = st.secrets.get("GEMINI_API_KEY")
    with st.form("gen"):
        p_name = st.text_input("ชื่อสินค้า")
        # (เพิ่มส่วน upload รูปและ inputs อื่นๆ ตรงนี้ตามเดิม)
        submit = st.form_submit_button("🚀 สร้างสคริปต์")
        if submit:
             st.success("ทำงานเรียบร้อย!")
             # เรียก generate_script ที่นี่

if st.session_state.logged_in:
    main_app()
else:
    login_screen()
