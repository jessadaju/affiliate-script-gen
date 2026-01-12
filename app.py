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
import smtplib
from email.mime.text import MIMEText
from email.header import Header  # สำคัญ! สำหรับแก้ปัญหาภาษาไทยในหัวข้ออีเมล
import random
import time

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Gen Pro (Verified)", page_icon="🔒", layout="centered")

# --- 2. ระบบอีเมล (Email Service - UTF-8 Fixed) ---
def send_verification_email(to_email, otp_code):
    """ส่งอีเมล OTP หาผู้สมัคร (รองรับภาษาไทยสมบูรณ์แบบ)"""
    try:
        if "email" not in st.secrets:
            st.error("❌ ไม่พบการตั้งค่าอีเมลใน Secrets")
            return False

        sender_email = st.secrets["email"]["sender_email"]
        sender_password = st.secrets["email"]["sender_password"]
        
        # หัวข้อและเนื้อหาอีเมล (ภาษาไทย)
        subject = "รหัสยืนยันตัวตน (OTP) - Affiliate Gen Pro"
        body = f"""
        สวัสดีครับ,
        
        รหัสยืนยันตัวตน (OTP) ของคุณคือ: {otp_code}
        
        รหัสนี้ใช้สำหรับการสมัครสมาชิกเท่านั้น (มีอายุ 5 นาที)
        ขอบคุณครับ
        """
        
        # ⚠️ แก้ไข: ระบุ encoding='utf-8' เพื่อให้รองรับภาษาไทยในเนื้อหา
        msg = MIMEText(body, 'plain', 'utf-8')
        
        # ⚠️ แก้ไข: ใช้ Header เพื่อรองรับภาษาไทยในหัวข้ออีเมล
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = sender_email
        msg['To'] = to_email

        # เชื่อมต่อ Server Gmail
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"ส่งอีเมลไม่สำเร็จ: {e}")
        return False

# --- 3. ระบบฐานข้อมูล (Google Sheets) ---
SHEET_NAME = "user_db"

def connect_to_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets: return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except: return None

def check_user_exists(username):
    """เช็กว่ามี user นี้หรือยัง (โดยยังไม่บันทึก)"""
    sheet = connect_to_gsheet()
    if not sheet: return True # กันเหนียวไว้ก่อน
    try:
        existing_users = sheet.col_values(1)
        return username in existing_users
    except: return True

def register_user_final(username, password, email):
    """บันทึกข้อมูลจริงหลังจาก Verify ผ่านแล้ว"""
    sheet = connect_to_gsheet()
    if not sheet: return False
    try:
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([username, hashed_pw, email, today])
        return True
    except: return False

def login_user(username, password):
    sheet = connect_to_gsheet()
    if not sheet: return None
    try:
        try:
            cell = sheet.find(username)
        except: return None
        if cell:
            row_data = sheet.row_values(cell.row)
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            if row_data[1] == hashed_pw: return row_data 
        return None
    except: return None

def check_trial(start_date_str):
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        diff = (datetime.datetime.now() - start_date).days
        return diff, 3 - diff
    except: return 0, 3

# --- 4. ระบบ AI ---
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
            # JSON-LD
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
            return title.strip(), desc
        return None, "Error"
    except: return None, "Error"

def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    prompt_text = f"""
    Role: Professional Ad Director & Sora AI Expert.
    Task: Create a Thai video script and Sora Prompts for '{product}'.
    Data: {features} {url_info} Tone: {tone}
    
    Output Format:
    ## 📝 Viral Caption (Thai)
    [Caption 2 lines]
    [Hashtags]

    ## 🎬 Script & Sora Prompts
    (4 Scenes: Hook, Pain, Solution, CTA)
    Format per scene:
    ### Scene X: [Name]
    **🗣️ Speak (Thai):** ...
    **🎥 Sora Prompt (English - Detailed):** ```text
    [Detailed visual description]
    ```
    """
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**Vision Instruction:** Analyze the image to write accurate Sora Prompts matching the real product."
        except: pass

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    return model.generate_content(contents).text

# --- 5. UI & Logic ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

# สถานะสำหรับการสมัครสมาชิก (Multi-step Registration)
if 'reg_stage' not in st.session_state: st.session_state.reg_stage = 1
if 'reg_otp' not in st.session_state: st.session_state.reg_otp = None
if 'reg_data' not in st.session_state: st.session_state.reg_data = {}

def login_screen():
    st.markdown("""
    <style>
        .main-card {background-color: #262730; padding: 2rem; border-radius: 10px; text-align: center; margin-bottom: 20px;}
        h1 {color: #4CAF50;}
    </style>
    <div class="main-card">
        <h1>🔒 Affiliate Gen Pro</h1>
        <p>Verified Secure Login</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "✨ สมัครสมาชิก (ยืนยันอีเมล)"])

    with tab1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", use_container_width=True):
                with st.spinner("Checking..."):
                    data = login_user(u, p)
                    if data:
                        used, left = check_trial(data[3])
                        if used > 3: st.error("หมดอายุการใช้งาน")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.user_info = {"name": data[0], "email": data[2], "left": left}
                            st.rerun()
                    else: st.error("ข้อมูลไม่ถูกต้อง")

    with tab2:
        # Step 1: กรอกข้อมูล
        if st.session_state.reg_stage == 1:
            with st.form("reg_step1"):
                new_u = st.text_input("ตั้งชื่อ Username *")
                new_e = st.text_input("อีเมล (เพื่อรับ OTP) *")
                new_p = st.text_input("ตั้งรหัส Password *", type="password")
                
                if st.form_submit_button("ส่งรหัสยืนยันไปที่อีเมล ->", use_container_width=True):
                    if new_u and new_e and new_p:
                        # 1. เช็กว่าชื่อซ้ำไหม
                        if check_user_exists(new_u):
                            st.warning("ชื่อ Username นี้มีคนใช้แล้ว")
                        else:
                            # 2. สร้าง OTP และส่งเมล
                            otp = str(random.randint(100000, 999999))
                            with st.spinner("กำลังส่งอีเมล..."):
                                if send_verification_email(new_e, otp):
                                    st.session_state.reg_otp = otp
                                    st.session_state.reg_data = {"u": new_u, "e": new_e, "p": new_p}
                                    st.session_state.reg_stage = 2
                                    st.success("✅ ส่งรหัสแล้ว! กรุณาเช็กอีเมล")
                                    time.sleep(1)
                                    st.rerun()
                    else:
                        st.warning("กรุณากรอกข้อมูลให้ครบ")

        # Step 2: กรอก OTP
        elif st.session_state.reg_stage == 2:
            st.info(f"📧 รหัสยืนยันถูกส่งไปที่: **{st.session_state.reg_data['e']}**")
            
            with st.form("reg_step2"):
                user_otp = st.text_input("กรอกรหัส OTP 6 หลัก", max_chars=6)
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_otp = st.form_submit_button("✅ ยืนยันและสมัคร", use_container_width=True)
                with col2:
                    cancel = st.form_submit_button("❌ ยกเลิก", use_container_width=True)
                
                if submit_otp:
                    if user_otp == st.session_state.reg_otp:
                        d = st.session_state.reg_data
                        if register_user_final(d['u'], d['p'], d['e']):
                            st.success("🎉 สมัครสมาชิกสำเร็จ!")
                            st.session_state.reg_stage = 1
                            st.session_state.reg_otp = None
                            st.session_state.reg_data = {}
                            time.sleep(2)
                            st.rerun()
                        else: st.error("บันทึกข้อมูลไม่สำเร็จ (ลองใหม่อีกครั้ง)")
                    else: st.error("❌ รหัส OTP ไม่ถูกต้อง")
                
                if cancel:
                    st.session_state.reg_stage = 1
                    st.rerun()

def main_app():
    info = st.session_state.user_info
    c1, c2 = st.columns([3, 1])
    with c1: st.info(f"👤 {info['name']} | ⏳ เหลือ {info['left']} วัน")
    with c2: 
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    my_api_key = st.secrets.get("GEMINI_API_KEY")

    # Scraper
    if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
    if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

    with st.expander("🔎 ดึงข้อมูลสินค้า (Optional)"):
        col_url, col_btn = st.columns([3, 1])
        with col_url: url = st.text_input("วางลิงก์ TikTok/Shopee")
        with col_btn:
            st.write(""); st.write("")
            if st.button("ดึงข้อมูล", use_container_width=True) and url:
                with st.spinner(".."):
                    t, d = scrape_web(url)
                    if t:
                        st.session_state.scraped_title = t
                        st.session_state.scraped_desc = d
                        st.success("✅")
                    else: st.warning("⚠️")

    with st.form("gen"):
        st.subheader("1. ข้อมูลสินค้า")
        p_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
        img_file = st.file_uploader("รูปสินค้า (Vision)", type=['png','jpg','webp'])
        if img_file: st.image(img_file, width=150)
        
        st.subheader("2. รายละเอียด")
        c1, c2 = st.columns(2)
        with c1: tone = st.selectbox("สไตล์", ["ตลก/ไวรัล", "Cinematic", "รีวิวพลีชีพ"])
        with c2: feat = st.text_area("จุดเด่น", value=st.session_state.scraped_desc, height=100)
        
        submit = st.form_submit_button("🚀 สร้างสคริปต์")
        if submit:
            if not my_api_key: st.error("❌ ไม่พบ API Key")
            elif not p_name and not img_file: st.warning("⚠️ ใส่ชื่อสินค้าด้วย")
            else:
                with st.spinner("🤖 AI กำลังทำงาน..."):
                    model = get_valid_model(my_api_key)
                    if model:
                        res = generate_script(my_api_key, model, p_name, feat, tone, url, img_file)
                        st.success("เสร็จเรียบร้อย!")
                        st.markdown(res)
                    else: st.error("AI Error")

# --- Run ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
