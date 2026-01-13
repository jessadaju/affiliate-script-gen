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
st.set_page_config(page_title="Affiliate Gen Pro (AI Brain)", page_icon="🧠", layout="centered")

# --- 2. Config & Constants ---
VALID_INVITE_CODES = ["VIP2024", "EARLYBIRD", "ADMIN"]
SHEET_NAME = "user_db"
ADMIN_USERNAME = "admin"

# --- 3. Database Functions (เหมือนเดิม) ---
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

# --- 4. AI Brain (ส่วนที่ฉลาดขึ้น 🧠) ---

def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # ใช้ 1.5 Pro เป็นตัวหลักเพราะฉลาดกว่า Flash มาก (แต่ถ้าช้าค่อยถอยไป Flash)
        preferred = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash']
        try:
            avail = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except: return preferred[0]
        for m in preferred:
            if m in avail: return m
        return avail[0] if avail else preferred[0]
    except: return None

def scrape_web(url):
    # เพิ่ม User-Agent ให้เนียนขึ้น
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

def generate_smart_script(api_key, model_name, product, features, tone, target_audience, platform, url_info, image_file=None):
    """
    ฟังก์ชันสมองกล:
    1. วิเคราะห์รูปภาพ (ถ้ามี) หาจุดขายทางสายตา
    2. วิเคราะห์กลุ่มเป้าหมาย (Target Audience)
    3. สร้าง 3 Hooks เพื่อเลือกสิ่งที่ดีที่สุด
    4. เขียน Prompt สำหรับ Sora แบบละเอียด (Cinematic)
    """
    
    # 🧠 Super Prompt Engineering
    prompt_text = f"""
    Act as a World-Class Creative Director & Viral Marketing Psychologist.
    You are creating a short video script for '{product}'.
    
    ## 🎯 Strategy Input
    - **Platform:** {platform} (Optimize for this algorithm)
    - **Target Audience:** {target_audience} (Use language that resonates with them)
    - **Tone:** {tone}
    - **Product Data:** {features} {url_info}
    
    ## 🖼️ Visual Analysis Instruction
    If an image is provided, analyze it deeply:
    - What is the material? (Matte, Glossy, Fabric textue?)
    - What is the lighting vibe?
    - **Crucial:** Ensure the 'Sora Prompts' describe the product EXACTLY as seen in the image to maintain consistency.

    ## 📝 Task Requirements
    1. **Psychological Analysis:** Briefly explain *why* this product solves the target audience's pain point.
    2. **3 Viral Hooks:** Create 3 different opening sentences (3 seconds) to stop the scroll (e.g., Shocking, Question, Story).
    3. **Main Script (Thai):** A cohesive story using the best hook.
    4. **Sora Prompts (English - Technical):** - Must use terms like: "Cinematic lighting", "Macro shot", "4k", "Depth of field".
       - Describe camera movement (e.g., "Slow pan", "Dolly zoom").
    
    ## 📤 Output Format (Strictly follow this)
    
    ### 🧠 AI Strategy Note
    *Thinking process: [Brief explanation of the strategy used]*

    ### 🎣 3 Hooks Options (Choose one)
    1. **Shocking:** ...
    2. **Relatable:** ...
    3. **Benefit-First:** ...

    ### 🎬 Final Video Script (Thai)
    **Caption:** [SEO Optimized Caption]
    **Hashtags:** [Trending Tags]

    #### Scene 1: The Hook (0-3s)
    **🗣️ Speak:** [Choose best hook]
    **🎥 Sora Prompt:** ```text
    [Technical English Prompt: Subject + Action + Lighting + Camera + Style]
    ```

    #### Scene 2: The Problem/Agitation (3-10s)
    **🗣️ Speak:** ...
    **🎥 Sora Prompt:** ```text
    [...]
    ```

    #### Scene 3: The Solution/Product Hero (10-20s)
    **🗣️ Speak:** ...
    **🎥 Sora Prompt:** ```text
    [...]
    ```

    #### Scene 4: Call to Action (20-30s)
    **🗣️ Speak:** ...
    **🎥 Sora Prompt:** ```text
    [...]
    ```
    """
    
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**[IMAGE ATTACHED]** Analyze this image for the visual prompts."
        except: pass

    genai.configure(api_key=api_key)
    # พยายามใช้ Model Pro เพื่อความฉลาดสูงสุด
    model = genai.GenerativeModel(model_name)
    return model.generate_content(contents).text

# --- 5. UI Logic ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

def renewal_screen():
    st.markdown("""
    <div style="background-color:#262730;padding:2rem;border-radius:10px;text-align:center;border:1px solid #FF4B4B;">
        <h2 style="color:#FF4B4B;">⚠️ หมดเวลาทดลองใช้</h2>
        <p>กรุณาติดต่อแอดมินเพื่อต่ออายุ</p>
    </div>
    """, unsafe_allow_html=True)
    if os.path.exists("payment_qr.jpg"): st.image("payment_qr.jpg", width=200)
    if st.button("⬅️ กลับ"): 
        st.session_state.logged_in = False
        st.rerun()

def admin_dashboard():
    st.markdown("### 🛠️ Admin Dashboard")
    with st.form("ext"):
        u = st.text_input("Username")
        d = st.selectbox("Days", [30, 90, 365, 3])
        if st.form_submit_button("Update"):
            if extend_user_subscription(u, d): st.success("Updated!")
            else: st.error("User not found")

def login_screen():
    st.markdown("<h1 style='text-align:center;'>🧠 Affiliate Gen Pro (AI Brain)</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        with st.form("l"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                d = login_user(u, p)
                if d:
                    us, le = check_status(d[3], d[5])
                    st.session_state.logged_in = True
                    st.session_state.user_info = {"name": d[0], "email": d[2], "left": le, "exp": le<=0}
                    st.rerun()
                else: st.error("Fail")
    with t2:
        with st.form("r"):
            nu = st.text_input("Username"); ne = st.text_input("Email"); np = st.text_input("Password", type="password"); c = st.text_input("Invite Code")
            if st.form_submit_button("Register"):
                if c in VALID_INVITE_CODES:
                    if not check_user_exists(nu):
                        if register_user(nu, np, ne, c): st.success("Success!"); time.sleep(1); st.rerun()
                    else: st.warning("Username taken")
                else: st.error("Invalid Code")

def main_app():
    i = st.session_state.user_info
    if i['name'] == ADMIN_USERNAME: admin_dashboard()
    if i['exp'] and i['name'] != ADMIN_USERNAME: renewal_screen(); return

    st.info(f"👤 {i['name']} | 🧠 AI Smart Mode | ⏳ {i['left']} Days")
    if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
    
    key = st.secrets.get("GEMINI_API_KEY")
    
    # Scraper
    if 's_t' not in st.session_state: st.session_state.s_t = ""
    if 's_d' not in st.session_state: st.session_state.s_d = ""
    with st.expander("🔎 ดึงข้อมูลสินค้า"):
        url = st.text_input("URL"); 
        if st.button("Scrape") and url:
            t, d = scrape_web(url)
            if t: st.session_state.s_t = t; st.session_state.s_d = d; st.success("✅")

    # Smart Input Form
    with st.form("gen"):
        st.subheader("1. ข้อมูลสินค้า")
        pn = st.text_input("ชื่อสินค้า", value=st.session_state.s_t)
        img = st.file_uploader("รูปสินค้า (ให้ AI วิเคราะห์)", type=['png','jpg','webp'])
        if img: st.image(img, width=150)
        
        st.subheader("2. กลยุทธ์ (AI Strategy)")
        c1, c2 = st.columns(2)
        with c1: 
            tone = st.selectbox("โทน/อารมณ์", ["ตลก/ไวรัล (Funny)", "หรูหรา/พรีเมียม (Luxury)", "เป็นกันเอง/เพื่อนสาว (Friendly)", "ดราม่า/เล่าเรื่อง (Storytelling)"])
            platform = st.selectbox("แพลตฟอร์ม", ["TikTok (เน้นเร็ว/เพลง)", "Facebook Reels (เน้นคนดูโต)", "YouTube Shorts (เน้นข้อมูล)"])
        with c2: 
            # เพิ่มช่องกลุ่มเป้าหมาย เพื่อให้ AI แม่นยำขึ้น
            target = st.text_input("กลุ่มเป้าหมาย (Target Audience)", placeholder="เช่น แม่บ้าน, วัยรุ่น, คนทำงานออฟฟิศ")
            feat = st.text_area("จุดเด่นสินค้า", value=st.session_state.s_d, height=100)
        
        if st.form_submit_button("🧠 ใช้สมอง AI สร้างสคริปต์"):
            if key:
                if not pn: st.warning("ใส่ชื่อสินค้าหน่อยครับ")
                else:
                    with st.spinner("🤖 AI กำลังวิเคราะห์จิตวิทยาและเขียนบท..."):
                        model = get_valid_model(key)
                        # เรียกฟังก์ชันใหม่ generate_smart_script
                        res = generate_smart_script(key, model, pn, feat, tone, target, platform, url, img)
                        st.success("เสร็จสิ้น!")
                        st.markdown(res)

if st.session_state.logged_in: main_app()
else: login_screen()
