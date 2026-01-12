import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image
import sqlite3
import datetime
import hashlib
import time

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script & Sora Gen", page_icon="🎥", layout="centered")

# --- 2. ระบบฐานข้อมูล (SQLite) สำหรับ Login ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, start_date TEXT)''')
    conn.commit()
    conn.close()

def register_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hashed_pw, today))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_pw))
    data = c.fetchone()
    conn.close()
    return data # (username, password, start_date)

def check_trial(start_date_str):
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    now = datetime.datetime.now()
    diff = (now - start_date).days
    return diff, 3 - diff # (ใช้ไปแล้ว, เหลืออีก)

# เริ่มต้นสร้าง DB ทันทีที่รันแอป
init_db()

# --- 3. ฟังก์ชัน AI & Scraper (Core System) ---

def get_valid_model(api_key):
    """ระบบค้นหาโมเดลอัตโนมัติ แก้ปัญหา Error 404"""
    try:
        genai.configure(api_key=api_key)
        # ลำดับโมเดลที่ต้องการ (1.5 Flash เร็วและเก่ง Vision)
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        
        # พยายามดึง list โมเดลที่มี (ถ้าดึงไม่ได้ให้ใช้ Default)
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except:
            return preferred_order[0]

        for model_name in preferred_order:
            if model_name in available_models: return model_name
        
        return available_models[0] if available_models else 'models/gemini-1.5-flash'
    except: return None

def scrape_web(url):
    """ระบบดึงข้อมูลเว็บ ทะลุ Cloudflare + อ่าน JSON-LD"""
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

            # สูตร 3: Title ปกติ
            if not final_title and soup.title: final_title = soup.title.string

            clean_title = final_title.split('|')[0].split(' - ')[0].strip()
            if clean_title: return clean_title, final_desc
            else: return None, "เว็บป้องกันหนาแน่น ไม่พบข้อมูล"
        else: return None, f"เข้าเว็บไม่ได้ (Status: {response.status_code})"
    except Exception as e: return None, f"Error: {str(e)}"

def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    """สร้างสคริปต์ไทย + Sora Prompt"""
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

# --- 4. ส่วน User Interface (UI) ---

# ตรวจสอบสถานะ Login
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

# ฟังก์ชันหน้า Login
def login_screen():
    st.markdown("""
    <style>
        .main-card {background-color: #1E1E1E; padding: 2rem; border-radius: 15px; border: 1px solid #333; text-align: center; margin-bottom: 2rem;}
        .title {color: #FF4B4B; font-size: 2rem; font-weight: bold;}
        .subtitle {color: #DDD;}
    </style>
    <div class="main-card">
        <div class="title">🎥 Affiliate Sora Gen</div>
        <div class="subtitle">เครื่องมือสร้างสคริปต์ AI สำหรับนักขายมืออาชีพ</div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "✨ สมัครใหม่ (ทดลองฟรี 3 วัน)"])

    with tab1:
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", use_container_width=True):
                data = login_user(user, pw)
                if data:
                    used, left = check_trial(data[2])
                    if used > 3:
                        st.error(f"หมดเวลาทดลองใช้ (ใช้ไป {used} วัน)")
                        st.info("กรุณาติดต่อแอดมินเพื่อต่ออายุ")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_info = {"name": user, "left": left}
                        st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านผิด")

    with tab2:
        with st.form("register"):
            new_u = st.text_input("ตั้งชื่อ Username")
            new_p = st.text_input("ตั้งรหัส Password", type="password")
            if st.form_submit_button("สมัครสมาชิก", use_container_width=True):
                if register_user(new_u, new_p):
                    st.success("สมัครสำเร็จ! กรุณาเข้าสู่ระบบ")
                else:
                    st.warning("ชื่อนี้ถูกใช้ไปแล้ว")

# ฟังก์ชันหน้าแอปหลัก (SaaS)
def main_app():
    # Header & Logout
    info = st.session_state.user_info
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.info(f"👤 ผู้ใช้: **{info['name']}** | ⏳ เหลือ: **{info['left']} วัน**")
    with col_b:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # พยายามดึง API Key จาก Secrets
    my_api_key = None
    if "GEMINI_API_KEY" in st.secrets:
        my_api_key = st.secrets["GEMINI_API_KEY"]
    else:
        # ถ้าไม่มีใน Secrets ให้กรอกเอง (เผื่อรัน Local)
        my_api_key = st.sidebar.text_input("Admin API Key", type="password")

    # ส่วนดึงข้อมูลเว็บ
    if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
    if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

    with st.expander("🔎 ดึงข้อมูลสินค้าจากลิงก์ (Optional)"):
        c1, c2 = st.columns([3, 1])
        with c1: url = st.text_input("วางลิงก์ TikTok/Shopee")
        with c2: 
            st.write("")
            st.write("")
            if st.button("ดึงข้อมูล", use_container_width=True) and url:
                with st.spinner("กำลังเจาะระบบ..."):
                    t, d = scrape_web(url)
                    if t:
                        st.session_state.scraped_title = t
                        st.session_state.scraped_desc = d
                        st.success("✅ ดึงสำเร็จ")
                    else: st.warning("⚠️ ไม่พบข้อมูล")

    # ฟอร์มหลัก
    with st.form("gen_form"):
        st.subheader("1. ข้อมูลสินค้า")
        p_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
        
        st.markdown("**📸 รูปสินค้า (เพื่อ Sora Prompt ที่แม่นยำ)**")
        img_file = st.file_uploader("อัปโหลดรูป", type=['png', 'jpg', 'jpeg', 'webp'])
        if img_file: st.image(img_file, width=150)
        
        st.subheader("2. รายละเอียด")
        c1, c2 = st.columns(2)
        with c1: tone = st.selectbox("สไตล์", ["ตลก/ไวรัล", "Cinematic สวยงาม", "รีวิวพลีชีพ", "Vlog เล่าเรื่อง"])
        with c2: feat = st.text_area("จุดเด่น", value=st.session_state.scraped_desc, height=100)
        
        submit = st.form_submit_button("🚀 สร้างสคริปต์ + Sora Prompt", use_container_width=True)

    if submit:
        if not my_api_key: st.error("❌ ไม่พบ API Key (กรุณาตั้งค่าใน Secrets)")
        elif not p_name and not img_file: st.warning("⚠️ กรุณาใส่ชื่อสินค้า")
        else:
            with st.spinner("🤖 AI กำลังทำงาน..."):
                model = get_valid_model(my_api_key)
                if model:
                    res = generate_script(my_api_key, model, p_name, feat, tone, url, img_file)
                    st.success("เรียบร้อย!")
                    st.markdown("---")
                    st.markdown(res)
                else: st.error("เชื่อมต่อ AI ไม่ได้")

# --- 5. Main Control ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
