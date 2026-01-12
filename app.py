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
import time
import os

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Gen Pro", page_icon="💎", layout="centered")

# --- 2. Config & Constants ---
VALID_INVITE_CODES = ["VIP2024", "EARLYBIRD", "ADMIN"]
SHEET_NAME = "user_db"
ADMIN_USERNAME = "admin" # ⚠️ อย่าลืมสมัคร User ชื่อ admin ไว้ใช้เองด้วยนะครับ

# --- 3. Google Sheets Database ---
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
    sheet = connect_to_gsheet()
    if not sheet: return True
    try:
        existing_users = sheet.col_values(1)
        return username in existing_users
    except: return True

def register_user(username, password, email, invite_code):
    sheet = connect_to_gsheet()
    if not sheet: return False
    try:
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        # Structure: [User, Pass, Email, StartDate, InviteCode, PlanDays]
        sheet.append_row([username, hashed_pw, email, today, invite_code, "3"])
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
            if row_data[1] == hashed_pw:
                if len(row_data) < 6: row_data.append("3")
                return row_data 
        return None
    except: return None

def extend_user_subscription(target_username, days_to_add):
    """ฟังก์ชันสำหรับแอดมิน: ต่ออายุ"""
    sheet = connect_to_gsheet()
    if not sheet: return False
    try:
        cell = sheet.find(target_username)
        if cell:
            row = cell.row
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            sheet.update_cell(row, 4, today) 
            sheet.update_cell(row, 6, str(days_to_add))
            return True
        return False
    except: return False

def check_status(start_date_str, plan_days_str):
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        plan_days = int(plan_days_str)
        now = datetime.datetime.now()
        diff = (now - start_date).days
        remaining = plan_days - diff
        return diff, remaining
    except: return 0, 0

# --- 4. AI & Scraper ---
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

# --- 5. UI Logic (Updated Pricing) ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

def renewal_screen():
    """หน้าจอแสดงราคาและ QR Code"""
    st.markdown("""
    <style>
        .price-card {
            background-color: #333;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #555;
            height: 100%;
        }
        .best-value {
            border: 2px solid #4CAF50;
            background-color: #1E3A23;
        }
        .price-title { font-size: 1.2rem; font-weight: bold; color: #DDD; }
        .price-tag { font-size: 1.8rem; font-weight: bold; color: #FF4B4B; margin: 10px 0; }
        .price-desc { font-size: 0.9rem; color: #AAA; }
    </style>
    <div style="text-align:center; margin-bottom:20px;">
        <h2 style="color:#FF4B4B;">⚠️ แพ็กเกจหมดอายุ</h2>
        <p>เลือกแพ็กเกจเพื่อใช้งานต่อ</p>
    </div>
    """, unsafe_allow_html=True)

    # --- ตารางราคา ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="price-card">
            <div class="price-title">Starter</div>
            <div class="price-tag">59฿</div>
            <div class="price-desc">7 วัน</div>
            <hr>
            <small>เหมาะสำหรับทดลอง</small>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="price-card">
            <div class="price-title">Standard</div>
            <div class="price-tag">99฿</div>
            <div class="price-desc">15 วัน</div>
            <hr>
            <small>คุ้มค่ายิ่งขึ้น</small>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="price-card best-value">
            <div style="color:#4CAF50; font-weight:bold; margin-bottom:5px;">🔥 ขายดีที่สุด</div>
            <div class="price-title">Pro Max</div>
            <div class="price-tag">169฿</div>
            <div class="price-desc">30 วัน</div>
            <hr>
            <small>เฉลี่ยวันละ 5 บาท</small>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.write("")
    
    # --- ส่วนชำระเงิน ---
    st.markdown("### 📲 ช่องทางการชำระเงิน")
    c_qr, c_info = st.columns([1, 2])
    
    with c_qr:
        # ใส่รูป QR Code ของคุณที่ชื่อ payment_qr.jpg
        if os.path.exists("payment_qr.jpg"):
            st.image("payment_qr.jpg", caption="สแกนจ่ายได้เลย", use_container_width=True)
        else:
            st.warning("No QR Code Image")
    
    with c_info:
        st.info("""
        **ขั้นตอนการต่ออายุ:**
        1. เลือกแพ็กเกจที่ต้องการ
        2. สแกน QR Code หรือโอนเงิน
        3. ส่งสลิปมาที่ **LINE ID: @YourLine**
        4. แจ้ง **Username** ของคุณกับแอดมิน
        
        *แอดมินจะทำการต่ออายุให้ภายใน 5 นาที*
        """)
        
        if st.button("⬅️ กลับหน้า Login"):
            st.session_state.logged_in = False
            st.rerun()

def admin_dashboard():
    """หน้าจัดการแอดมิน"""
    st.markdown("### 🛠️ Admin Dashboard")
    st.info("จัดการต่ออายุสมาชิก")
    
    with st.form("extend_form"):
        target_user = st.text_input("ระบุ Username ลูกค้า")
        # ตัวเลือกวันต้องตรงกับแพ็กเกจ
        days_option = st.selectbox("เลือกแพ็กเกจที่จะเติม", 
                                   ["7 วัน (59฿)", "15 วัน (99฿)", "30 วัน (169฿)", "ปลดล็อกพิเศษ (365 วัน)"])
        
        # แปลงตัวเลือกเป็นตัวเลข
        days_map = {
            "7 วัน (59฿)": 7,
            "15 วัน (99฿)": 15,
            "30 วัน (169฿)": 30,
            "ปลดล็อกพิเศษ (365 วัน)": 365
        }
        
        if st.form_submit_button("✅ อนุมัติ / ต่ออายุ"):
            if target_user:
                days_to_add = days_map[days_option]
                with st.spinner("กำลังอัปเดตข้อมูล..."):
                    if extend_user_subscription(target_user, days_to_add):
                        st.success(f"ต่ออายุให้ {target_user} เพิ่ม {days_to_add} วัน เรียบร้อย!")
                    else:
                        st.error("ไม่พบ Username นี้ในระบบ")
            else:
                st.warning("กรุณาใส่ชื่อ Username")

def login_screen():
    st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <h1>💎 Affiliate Gen Pro</h1>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Register (Invite Only)"])

    with tab1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("เข้าสู่ระบบ", use_container_width=True):
                data = login_user(u, p)
                if data:
                    used, left = check_status(data[3], data[5])
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        "name": data[0], 
                        "email": data[2], 
                        "left": left,
                        "is_expired": left <= 0
                    }
                    st.rerun()
                else: st.error("ข้อมูลผิดพลาด")

    with tab2:
        with st.form("reg"):
            st.caption("ต้องใช้รหัสเชิญเท่านั้น")
            new_u = st.text_input("Username *")
            new_e = st.text_input("Email *")
            new_p = st.text_input("Password *", type="password")
            code = st.text_input("Invite Code *")
            
            if st.form_submit_button("สมัครสมาชิก"):
                if code in VALID_INVITE_CODES:
                    if check_user_exists(new_u):
                        st.warning("ชื่อซ้ำ")
                    else:
                        if register_user(new_u, new_p, new_e, code):
                            st.success("สมัครสำเร็จ! (ทดลองใช้ฟรี 3 วัน)")
                            time.sleep(2)
                            st.rerun()
                        else: st.error("Error")
                else: st.error("รหัสเชิญผิด")

def main_app():
    info = st.session_state.user_info
    
    # Admin Mode
    if info['name'] == ADMIN_USERNAME:
        st.warning("👨‍💻 Admin Mode")
        admin_dashboard()
        st.markdown("---")

    # Expired User
    if info['is_expired'] and info['name'] != ADMIN_USERNAME:
        renewal_screen()
        return

    # Normal User
    c1, c2 = st.columns([3, 1])
    with c1: st.info(f"👤 {info['name']} | ✅ สถานะปกติ (เหลือ {info['left']} วัน)")
    with c2: 
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
            
    my_api_key = st.secrets.get("GEMINI_API_KEY")
    
    with st.expander("🔎 ดึงข้อมูลสินค้า"):
        url = st.text_input("URL สินค้า")
        if st.button("ดึงข้อมูล") and url:
            t, d = scrape_web(url)
            if t:
                st.session_state.scraped_title = t
                st.session_state.scraped_desc = d
                st.success("✅")
    
    with st.form("gen"):
        st.subheader("สร้างสคริปต์")
        p_name = st.text_input("ชื่อสินค้า", value=st.session_state.get('scraped_title',''))
        img_file = st.file_uploader("รูปสินค้า", type=['png','jpg'])
        if img_file: st.image(img_file, width=150)
        tone = st.selectbox("สไตล์", ["ตลก", "จริงจัง", "รีวิวพลีชีพ"])
        feat = st.text_area("จุดเด่น", value=st.session_state.get('scraped_desc',''))
        
        if st.form_submit_button("🚀 Start"):
            if my_api_key:
                with st.spinner("AI Working..."):
                    model = get_valid_model(my_api_key)
                    res = generate_script(my_api_key, model, p_name, feat, tone, url, img_file)
                    st.markdown(res)

if st.session_state.logged_in:
    main_app()
else:
    login_screen()
