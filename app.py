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
st.set_page_config(page_title="Affiliate Script & Sora Gen (Pro)", page_icon="🎥", layout="centered")

# --- 2. ระบบฐานข้อมูล (Google Sheets) ---
SHEET_NAME = "user_db" # ชื่อไฟล์ Google Sheet

def connect_to_gsheet():
    """เชื่อมต่อ Google Sheets โดยอ่านจาก Secrets"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if "gcp_service_account" not in st.secrets:
            st.error("❌ ไม่พบข้อมูล Secrets (gcp_service_account)")
            return None

        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

def register_user(username, password, email):
    """สมัครสมาชิกแบบบันทึกลง Sheet"""
    sheet = connect_to_gsheet()
    if not sheet: return False

    try:
        # เช็ก Username ซ้ำ
        existing_users = sheet.col_values(1)
        if username in existing_users: return False 
        
        # บันทึก
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([username, hashed_pw, email, today])
        return True
    except: return False

def login_user(username, password):
    """ล็อกอินโดยดึงข้อมูลจาก Sheet"""
    sheet = connect_to_gsheet()
    if not sheet: return None

    try:
        try:
            cell = sheet.find(username)
        except gspread.exceptions.CellNotFound:
            return None

        if cell:
            row_data = sheet.row_values(cell.row)
            # row_data = [username, password_hash, email, start_date]
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            if row_data[1] == hashed_pw:
                return row_data 
        return None
    except: return None

def check_trial(start_date_str):
    """คำนวณวันทดลองใช้"""
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        now = datetime.datetime.now()
        diff = (now - start_date).days
        return diff, 3 - diff
    except: return 0, 3

# --- 3. ฟังก์ชัน AI Core System ---

def get_valid_model(api_key):
    """หาโมเดลอัตโนมัติ"""
    try:
        genai.configure(api_key=api_key)
        preferred = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        try:
            avail = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except: return preferred[0]
        for m in preferred:
            if m in avail: return m
        return avail[0] if avail else preferred[0]
    except: return None

def scrape_web(url):
    """ดึงข้อมูลเว็บเทพ (Cloudscraper + JSON-LD)"""
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            final_title, final_desc = "", ""

            # สูตร 1: JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if '@type' in data and data['@type'] == 'Product':
                        final_title = data.get('name', '')
                        final_desc = data.get('description', '')
                        break
                    if '@type' in data and data['@type'] == 'BreadcrumbList':
                        if 'itemListElement' in data: final_title = data['itemListElement'][-1]['item']['name']
                except: continue

            # สูตร 2: Open Graph
            if not final_title:
                og_title = soup.find('meta', property='og:title')
                if og_title: final_title = og_title.get('content', '')
            if not final_desc:
                og_desc = soup.find('meta', property='og:description')
                if og_desc: final_desc = og_desc.get('content', '')

            if not final_title and soup.title: final_title = soup.title.string

            clean_title = final_title.split('|')[0].split(' - ')[0].strip()
            if clean_title: return clean_title, final_desc
            else: return None, "เว็บป้องกันหนาแน่น ไม่พบข้อมูล"
        else: return None, f"เข้าเว็บไม่ได้ ({response.status_code})"
    except Exception as e: return None, f"Error: {str(e)}"

def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    """สร้างสคริปต์ไทย + Sora Prompt + Vision"""
    prompt_text = f"""
    Role: ผู้กำกับภาพยนตร์โฆษณา และผู้เชี่ยวชาญด้าน Sora AI (Video Generative AI).
    Task: วางแผนถ่ายทำคลิปวิดีโอสั้นสำหรับสินค้า: '{product}'.
    Language: **ภาษาไทยทั้งหมด** (ทั้งบทพูด และ คำสั่งสร้างภาพ).
    
    ข้อมูลสินค้า: {product}
    ข้อมูลเพิ่มเติม: {features} {url_info}
    อารมณ์/โทน: {tone}
    
    Output Format:
    ## 📝 แคปชั่น & แฮชแทค (Viral SEO)
    [แคปชั่นภาษาไทย 2 บรรทัด เน้นหยุดนิ้วโป้ง]
    [แฮชแทค]

    ## 🎬 สคริปต์และคำสั่งสร้างภาพ (Sora AI)
    (4 Scenes: Hook, Pain, Solution, CTA)
    
    Format per scene:
    ### ฉากที่ X: [ชื่อฉาก]
    **🗣️ บทพูด:** ...
    **🎥 คำสั่ง Sora (Prompt):** ```text
    [คำบรรยายภาพภาษาไทย ใส่รายละเอียดแสง มุมกล้อง การเคลื่อนไหว แบบละเอียด เพื่อให้คนนำไป Gen Video ได้เลย]
    ```
    """
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**คำสั่ง Vision:** วิเคราะห์รูปภาพ แล้วเขียนคำสั่ง Sora ให้ตรงปกที่สุด (สี/ทรง/วัสดุ ต้องเป๊ะตามรูป)"
        except: pass

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(contents)
    return response.text

# --- 4. User Interface (UI) ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

def login_screen():
    st.markdown("""
    <style>
        .main-card {background-color: #262730; padding: 2rem; border-radius: 10px; text-align: center; margin-bottom: 20px;}
        h1 {color: #FF4B4B;}
    </style>
    <div class="main-card">
        <h1>💎 Affiliate Gen Pro</h1>
        <p>ระบบสมาชิก & ทดลองฟรี 3 วัน</p>
    </div>
    """, unsafe_allow_html=True)
    
    # --- ส่วนที่ถูกลบ: ปุ่มเช็กสถานะ Server หายไปแล้ว ---

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
                            st.error(f"หมดอายุ (ใช้ไป {used} วัน) กรุณาติดต่อแอดมิน")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.user_info = {"name": data[0], "email": data[2], "left": left}
                            st.rerun()
                    else:
                        st.error("ไม่พบข้อมูล หรือ รหัสผิด")

    with tab2:
        with st.form("reg"):
            new_u = st.text_input("Username *")
            new_e = st.text_input("Email *")
            new_p = st.text_input("Password *", type="password")
            if st.form_submit_button("สมัครสมาชิก", use_container_width=True):
                if new_u and new_e and new_p:
                    with st.spinner("กำลังบันทึกข้อมูล..."):
                        if register_user(new_u, new_p, new_e):
                            st.success("✅ สมัครสำเร็จ! กรุณากลับไปหน้า Login")
                        else:
                            st.error("สมัครไม่ผ่าน (ชื่ออาจซ้ำ หรือระบบขัดข้อง)")
                else:
                    st.warning("กรอกข้อมูลให้ครบถ้วนนะครับ")

def main_app():
    # Header
    info = st.session_state.user_info
    c1, c2 = st.columns([3, 1])
    with c1: st.info(f"👤 {info['name']} | ⏳ เหลือ {info['left']} วัน")
    with c2: 
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # API Key
    my_api_key = st.secrets.get("GEMINI_API_KEY")

    # Scraper Section
    if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
    if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

    with st.expander("🔎 ดึงข้อมูลสินค้า (Optional)"):
        col_url, col_btn = st.columns([3, 1])
        with col_url: url = st.text_input("วางลิงก์ TikTok/Shopee")
        with col_btn:
            st.write(""); st.write("")
            if st.button("ดึงข้อมูล", use_container_width=True) and url:
                with st.spinner("กำลังเจาะระบบ..."):
                    t, d = scrape_web(url)
                    if t:
                        st.session_state.scraped_title = t
                        st.session_state.scraped_desc = d
                        st.success("✅ ดึงข้อมูลสำเร็จ")
                    else: st.warning("⚠️ ไม่พบข้อมูล (กรอกเองได้เลย)")

    # Main Form
    with st.form("gen_form"):
        st.subheader("1. ข้อมูลสินค้า")
        p_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
        
        st.markdown("**📸 อัปโหลดรูป (สำคัญสำหรับ Sora)**")
        img_file = st.file_uploader("เลือกรูป", type=['png', 'jpg', 'jpeg', 'webp'])
        if img_file: st.image(img_file, width=150)
        
        st.subheader("2. รายละเอียด")
        c1, c2 = st.columns(2)
        with c1: tone = st.selectbox("สไตล์", ["ตลก/ไวรัล", "Cinematic สวยงาม", "รีวิวพลีชีพ", "Vlog เล่าเรื่อง"])
        with c2: feat = st.text_area("จุดเด่น", value=st.session_state.scraped_desc, height=100)
        
        submit = st.form_submit_button("🚀 สร้างสคริปต์ + Sora Prompt", use_container_width=True)

    if submit:
        if not my_api_key: st.error("❌ ระบบขัดข้อง: ไม่พบ API Key (แจ้งแอดมิน)")
        elif not p_name and not img_file: st.warning("⚠️ กรุณาใส่ชื่อสินค้า หรืออัปโหลดรูปภาพ")
        else:
            with st.spinner("🤖 AI กำลังทำงาน..."):
                model = get_valid_model(my_api_key)
                if model:
                    res = generate_script(my_api_key, model, p_name, feat, tone, url, img_file)
                    st.success("เสร็จเรียบร้อย!")
                    st.markdown("---")
                    st.markdown(res)
                else: st.error("เชื่อมต่อ AI ไม่ได้")

# --- Main Control ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
I
