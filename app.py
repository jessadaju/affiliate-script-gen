import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image
import sqlite3
import datetime
import hashlib
import os

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script & Sora Gen", page_icon="🎥", layout="centered")

# --- 2. ระบบฐานข้อมูล (เพิ่ม Email & Auto-Restore) ---
DB_NAME = "users_v2.db" # เปลี่ยนชื่อ DB เพื่อเริ่มเก็บข้อมูลรูปแบบใหม่

def init_db():
    """สร้างฐานข้อมูลอัตโนมัติถ้าหาไม่เจอ"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # เพิ่มคอลัมน์ email เข้าไปในตาราง
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, email TEXT, start_date TEXT)''')
    conn.commit()
    conn.close()

def register_user(username, password, email):
    """สมัครสมาชิกพร้อมเก็บอีเมล"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, hashed_pw, email, today))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    """เช็กล็อกอิน"""
    # กันเหนียว: ถ้าไฟล์ DB หายไป (เพราะ Cloud รีสตาร์ท) ให้สร้างใหม่รอไว้ก่อน
    if not os.path.exists(DB_NAME):
        init_db()
        return None 

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_pw))
    data = c.fetchone()
    conn.close()
    return data # (username, password, email, start_date)

def check_trial(start_date_str):
    """คำนวณวันทดลองใช้คงเหลือ"""
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        now = datetime.datetime.now()
        diff = (now - start_date).days
        return diff, 3 - diff # (ใช้ไปแล้ว, เหลืออีก)
    except:
        return 0, 3 # ถ้าวันที่มีปัญหา ให้เริ่มนับใหม่

# เริ่มต้นเช็ก DB ทันที
init_db()

# --- 3. ฟังก์ชัน AI (Core System) ---
# ... (ส่วนนี้เหมือนเดิม ใช้ฟังก์ชันเดิมได้เลย) ...

def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except: return preferred_order[0]
        for model_name in preferred_order:
            if model_name in available_models: return model_name
        return available_models[0] if available_models else 'models/gemini-1.5-flash'
    except: return None

def scrape_web(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            final_title, final_desc = "", ""
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
    prompt_text = f"""
    Role: ผู้กำกับโฆษณา & Sora AI Expert.
    Task: ทำสคริปต์วิดีโอขายสินค้า: '{product}' ภาษาไทย.
    Inputs: {features} {url_info} Tone: {tone}
    Output:
    ## 📝 แคปชั่น & แฮชแทค
    [แคปชั่น 2 บรรทัด]
    [Hashtags]
    ## 🎬 สคริปต์ & Sora Prompts
    (4 Scenes: Hook, Pain, Solution, CTA)
    Format:
    ### ฉากที่ X: [ชื่อ]
    **🗣️ พูด:** ...
    **🎥 Sora Prompt:** ```text
    [คำบรรยายภาพละเอียด ภาษาไทย]
    ```
    """
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**Vision:** วิเคราะห์รูปภาพสินค้า แล้วเขียน Sora Prompt ให้ตรงปกที่สุด"
        except: pass
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(contents)
    return response.text

# --- 4. User Interface (UI) ---

# State Management
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

# ฟังก์ชันหน้า Login/Register (ปรับปรุงใหม่)
def login_screen():
    st.markdown("""
    <style>
        .main-card {background-color: #262730; padding: 2rem; border-radius: 10px; text-align: center; margin-bottom: 20px;}
        h1 {color: #FF4B4B;}
    </style>
    <div class="main-card">
        <h1>💎 Affiliate Gen Pro</h1>
        <p>เข้าสู่ระบบเพื่อใช้งาน / ทดลองฟรี 3 วัน</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก (เพิ่ม Email)"])

    with tab1:
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", use_container_width=True):
                data = login_user(user, pw)
                if data:
                    # data[3] คือ start_date
                    used, left = check_trial(data[3])
                    if used > 3:
                        st.error(f"หมดเวลาทดลองใช้ (ใช้ไป {used} วัน)")
                        st.info("กรุณาติดต่อแอดมินเพื่อต่ออายุ")
                    else:
                        st.session_state.logged_in = True
                        # data[0]=username, data[2]=email
                        st.session_state.user_info = {"name": data[0], "email": data[2], "left": left}
                        st.rerun()
                else:
                    st.error("ไม่พบข้อมูลผู้ใช้ หรือ รหัสผ่านผิด (หากเพิ่งสมัคร ลองสมัครใหม่)")
    
    with tab2:
        st.caption("สมัครใหม่วันนี้ ทดลองใช้ฟรี 3 วันเต็ม!")
        with st.form("register"):
            new_u = st.text_input("ตั้งชื่อ Username *", placeholder="ภาษาอังกฤษเท่านั้น")
            new_email = st.text_input("อีเมล (Email) *", placeholder="example@gmail.com") # เพิ่มช่อง Email
            new_p = st.text_input("ตั้งรหัส Password *", type="password")
            
            if st.form_submit_button("✅ สมัครและเริ่มใช้งานทันที", use_container_width=True):
                if new_u and new_p and new_email:
                    if register_user(new_u, new_p, new_email):
                        st.success("🎉 สมัครสำเร็จ! กรุณาไปที่แท็บ 'เข้าสู่ระบบ' เพื่อ Login ได้เลยครับ")
                    else:
                        st.warning("ชื่อ Username นี้มีคนใช้แล้วครับ")
                else:
                    st.error("กรุณากรอกข้อมูลให้ครบทุกช่อง")

# ฟังก์ชันแอปหลัก
def main_app():
    info = st.session_state.user_info
    
    # Header ส่วนตัว
    with st.container():
        c1, c2 = st.columns([3, 1])
        with c1:
            st.info(f"👤 ผู้ใช้: **{info['name']}** ({info.get('email', '-')}) | ⏳ เหลือ: **{info['left']} วัน**")
        with c2:
            if st.button("🚪 Logout"):
                st.session_state.logged_in = False
                st.rerun()

    # API Key Management
    my_api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not my_api_key:
        my_api_key = st.sidebar.text_input("Admin API Key (ใส่ตรงนี้ถ้ายังไม่ตั้ง Secrets)", type="password")

    # State for Scraper
    if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
    if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

    # Scraper UI
    with st.expander("🔎 ดึงข้อมูลสินค้า (Optional)"):
        c1, c2 = st.columns([3, 1])
        with c1: url = st.text_input("ลิงก์สินค้า TikTok/Shopee")
        with c2: 
            st.write(""); st.write("")
            if st.button("ดึงข้อมูล", use_container_width=True) and url:
                with st.spinner(".."):
                    t, d = scrape_web(url)
                    if t:
                        st.session_state.scraped_title = t
                        st.session_state.scraped_desc = d
                        st.success("✅")
                    else: st.warning("⚠️")

    # Main Form
    with st.form("gen"):
        st.subheader("1. ข้อมูลสินค้า")
        p_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
        img_file = st.file_uploader("รูปสินค้า (เพื่อ Sora Prompt)", type=['png','jpg','webp'])
        if img_file: st.image(img_file, width=150)
        
        st.subheader("2. รายละเอียด")
        c1, c2 = st.columns(2)
        with c1: tone = st.selectbox("สไตล์", ["ตลก/ไวรัล", "Cinematic", "รีวิวพลีชีพ"])
        with c2: feat = st.text_area("จุดเด่น", value=st.session_state.scraped_desc, height=100)
        
        if st.form_submit_button("🚀 สร้างสคริปต์", use_container_width=True):
            if not my_api_key: st.error("❌ ไม่พบ API Key")
            elif not p_name and not img_file: st.warning("⚠️ ใส่ชื่อสินค้าก่อนนะ")
            else:
                with st.spinner("🤖 AI กำลังทำงาน..."):
                    model = get_valid_model(my_api_key)
                    if model:
                        res = generate_script(my_api_key, model, p_name, feat, tone, url, img_file)
                        st.success("เรียบร้อย!")
                        st.markdown(res)
                    else: st.error("AI Error")

# --- 5. Main Control ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
