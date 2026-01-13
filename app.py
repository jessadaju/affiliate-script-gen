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
st.set_page_config(page_title="Affiliate Gen Pro (Easy Copy)", page_icon="⚡", layout="centered")

# --- 2. Config & Constants ---
VALID_INVITE_CODES = ["VIP2024", "EARLYBIRD", "ADMIN"]
SHEET_NAME = "user_db"
ADMIN_USERNAME = "admin"

# --- 3. Database Functions ---
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

# --- 4. AI Brain (JSON Mode for Easy Copy) ---

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

def generate_smart_script_json(api_key, model_name, product, features, tone, target_audience, platform, url_info, image_file=None):
    """
    Generate script in JSON format for easy UI parsing.
    """
    
    # Prompt สั่งให้ตอบเป็น JSON เท่านั้น
    prompt_text = f"""
    Act as a Creative Director. Create a video script for '{product}'.
    
    Context:
    - Platform: {platform}
    - Target: {target_audience}
    - Tone: {tone}
    - Data: {features} {url_info}
    
    If image provided: Analyze texture/lighting for Sora prompts.

    **IMPORTANT:** Return ONLY valid JSON with this structure:
    {{
      "strategy": "Brief explanation of why this angle works",
      "hooks": ["Hook option 1", "Hook option 2", "Hook option 3"],
      "caption": "Viral caption text",
      "hashtags": "#tag1 #tag2 #tag3",
      "scenes": [
        {{
          "scene_name": "Scene 1: Hook",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English visual prompt..."
        }},
        {{
          "scene_name": "Scene 2: Problem",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English visual prompt..."
        }},
        {{
          "scene_name": "Scene 3: Solution",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English visual prompt..."
        }},
        {{
          "scene_name": "Scene 4: CTA",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English visual prompt..."
        }}
      ]
    }}
    """
    
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**[IMAGE ATTACHED]** Base visual prompts on this image."
        except: pass

    genai.configure(api_key=api_key)
    
    # บังคับ JSON Mode (เฉพาะ Gemini 1.5 ขึ้นไป)
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
    
    response = model.generate_content(contents)
    return response.text

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
    st.markdown("<h1 style='text-align:center;'>⚡ Affiliate Gen Pro</h1>", unsafe_allow_html=True)
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

    st.info(f"👤 {i['name']} | ⏳ {i['left']} Days Left")
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
        img = st.file_uploader("รูปสินค้า", type=['png','jpg','webp'])
        if img: st.image(img, width=150)
        
        st.subheader("2. กลยุทธ์")
        c1, c2 = st.columns(2)
        with c1: 
            tone = st.selectbox("โทน", ["ตลก/ไวรัล", "หรูหรา", "เพื่อนสาว", "ดราม่า"])
            platform = st.selectbox("แพลตฟอร์ม", ["TikTok", "Reels", "Shorts"])
        with c2: 
            target = st.text_input("กลุ่มเป้าหมาย", placeholder="เช่น แม่บ้าน, นร.")
            feat = st.text_area("จุดเด่น", value=st.session_state.s_d, height=100)
        
        if st.form_submit_button("⚡ สร้างสคริปต์ (แบบก๊อปง่าย)"):
            if key:
                if not pn: st.warning("ใส่ชื่อสินค้าหน่อยครับ")
                else:
                    with st.spinner("🤖 AI กำลังแยกชิ้นส่วนข้อมูล..."):
                        model = get_valid_model(key)
                        json_res = generate_smart_script_json(key, model, pn, feat, tone, target, platform, url, img)
                        
                        # Parse JSON
                        try:
                            data = json.loads(json_res)
                            
                            st.success("เสร็จสิ้น! กดปุ่ม Copy ที่มุมขวาบนของแต่ละกล่องได้เลย")
                            st.markdown("---")
                            
                            # 1. Strategy
                            st.info(f"🧠 **AI Strategy:** {data.get('strategy', '')}")
                            
                            # 2. Caption (Copyable)
                            st.subheader("📝 Caption & Hashtags")
                            full_caption = f"{data.get('caption', '')}\n\n{data.get('hashtags', '')}"
                            st.code(full_caption, language='text') # ใช้ st.code เพื่อให้มีปุ่ม copy
                            
                            # 3. Hooks
                            with st.expander("🎣 ทางเลือกเปิดคลิป (Hooks)", expanded=True):
                                for idx, hook in enumerate(data.get('hooks', [])):
                                    st.write(f"**Option {idx+1}:**")
                                    st.code(hook, language='text')

                            # 4. Scenes (Copyable Prompts)
                            st.subheader("🎬 Video Script & Sora Prompts")
                            for scene in data.get('scenes', []):
                                with st.container():
                                    st.markdown(f"**{scene.get('scene_name', 'Scene')}**")
                                    c1, c2 = st.columns([1, 1])
                                    with c1:
                                        st.caption("🗣️ บทพูด (ไทย)")
                                        st.info(scene.get('script_thai', '-'))
                                    with c2:
                                        st.caption("🎥 Sora Prompt (English - กด Copy มุมขวาบน)")
                                        # กล่องนี้แหละที่ลูกค้าต้องการ!
                                        st.code(scene.get('sora_prompt', ''), language="text")
                                    st.markdown("---")
                                    
                        except Exception as e:
                            st.error(f"เกิดข้อผิดพลาดในการแปลผล JSON: {e}")
                            st.text(json_res) # Show raw if error

if st.session_state.logged_in: main_app()
else: login_screen()
