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
import tempfile
from moviepy.editor import VideoFileClip, CompositeVideoClip

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Gen Pro (Video Max)", page_icon="🎬", layout="centered")

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

# --- 4. AI & Scraper Functions ---
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
    prompt_text = f"""
    Act as a Creative Director. Create a video script for '{product}'.
    Context: Platform: {platform}, Target: {target_audience}, Tone: {tone}, Data: {features} {url_info}
    If image provided: Analyze texture/lighting for Sora prompts.
    **IMPORTANT:** Return ONLY valid JSON with this structure:
    {{
      "strategy": "Brief explanation",
      "hooks": ["Hook 1", "Hook 2", "Hook 3"],
      "caption": "Viral caption",
      "hashtags": "#tag1 #tag2",
      "scenes": [
        {{ "scene_name": "Scene 1", "script_thai": "...", "sora_prompt": "..." }},
        {{ "scene_name": "Scene 2", "script_thai": "...", "sora_prompt": "..." }},
        {{ "scene_name": "Scene 3", "script_thai": "...", "sora_prompt": "..." }},
        {{ "scene_name": "Scene 4", "script_thai": "...", "sora_prompt": "..." }}
      ]
    }}
    """
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
        except: pass

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
    return model.generate_content(contents).text

# --- 5. Advanced Video Processing (High Quality + Moving Logo) ---

def pixelate_region(image, x, y, w, h, blocks=10):
    """ฟังก์ชันทำโมเสกเฉพาะจุด (Manual Pixelate)"""
    import cv2
    import numpy as np
    
    # Crop region
    sub_img = image[y:y+h, x:x+w]
    
    # Resize small
    h_sub, w_sub = sub_img.shape[:2]
    # ป้องกัน error กรณีขนาดเป็น 0
    if h_sub <= 0 or w_sub <= 0: return image
    
    small = cv2.resize(sub_img, (max(1, int(w_sub/blocks)), max(1, int(h_sub/blocks))), interpolation=cv2.INTER_LINEAR)
    # Resize back
    pixelated = cv2.resize(small, (w_sub, h_sub), interpolation=cv2.INTER_NEAREST)
    
    # Put back
    image[y:y+h, x:x+w] = pixelated
    return image

def process_video_advanced(video_path, blur_configs, quality_mode="High"):
    """
    blur_configs: list of dict -> [{'start':0, 'end':5, 'pos':'Top-Left'}, ...]
    quality_mode: 'Normal' (Fast), 'High' (Slow, Better Bitrate)
    """
    try:
        clip = VideoFileClip(video_path)
        w, h = clip.size
        
        # กำหนดขนาดกล่องที่จะเบลอ (ปรับได้)
        box_w = int(w * 0.3) 
        box_h = int(h * 0.15)

        def get_pos_coords(pos_name):
            if pos_name == 'Top-Left': return 0, 0
            if pos_name == 'Top-Center': return (w//2)-(box_w//2), 0
            if pos_name == 'Top-Right': return w - box_w, 0
            
            if pos_name == 'Middle-Left': return 0, (h//2)-(box_h//2)
            if pos_name == 'Center': return (w//2)-(box_w//2), (h//2)-(box_h//2)
            if pos_name == 'Middle-Right': return w - box_w, (h//2)-(box_h//2)
            
            if pos_name == 'Bottom-Left': return 0, h - box_h
            if pos_name == 'Bottom-Center': return (w//2)-(box_w//2), h - box_h
            if pos_name == 'Bottom-Right': return w - box_w, h - box_h
            return 0,0

        # ฟังก์ชันที่จะรันทุกเฟรม
        def frame_processor(get_frame, t):
            frame = get_frame(t).copy() # เอาภาพเฟรมปัจจุบันมา (ต้อง copy เพื่อไม่ให้เพี้ยน)
            
            # วนลูปเช็กว่าวินาทีนี้ (t) ต้องเบลอตรงไหนบ้าง
            for config in blur_configs:
                if config['start'] <= t <= config['end']:
                    px, py = get_pos_coords(config['pos'])
                    # สั่งเบลอ (Pixelate)
                    frame = pixelate_region(frame, px, py, box_w, box_h, blocks=15)
            
            return frame

        # สร้าง Clip ใหม่ที่ผ่านการประมวลผลเฟรม
        final_clip = clip.fl(frame_processor)
        
        # Output Config
        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        
        # High Quality Settings
        # bitrate: '5000k' = 5Mbps (ชัดมาก), '8000k' (ชัดโคตร)
        # preset: 'medium' (สมดุล), 'slow' (ชัดขึ้นแต่เรนเดอร์นาน), 'ultrafast' (แตกนิดหน่อยแต่เร็ว)
        
        if quality_mode == "High (Slow)":
            bitrate = "8000k"
            preset = "medium"
        else:
            bitrate = "3000k" # Standard
            preset = "ultrafast"

        final_clip.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac",
            bitrate=bitrate,
            preset=preset,
            fps=clip.fps # คง fps เดิมไว้
        )
        
        clip.close()
        return output_path
    except Exception as e:
        print(e)
        return None

# --- 6. UI Logic ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

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
    st.info(f"👤 {st.session_state.user_info['name']} | ⏳ {st.session_state.user_info['left']} Days Left")
    if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
    
    key = st.secrets.get("GEMINI_API_KEY")
    
    # Tabs
    tab_gen, tab_vid = st.tabs(["🚀 AI Script Generator", "🎬 Advanced Video Tools"])
    
    # --- Tab 1: AI (Code เดิม ย่อไว้) ---
    with tab_gen:
        if 's_t' not in st.session_state: st.session_state.s_t = ""
        with st.expander("🔎 Scrape Product"):
            url = st.text_input("URL"); 
            if st.button("Scrape") and url:
                t, d = scrape_web(url); 
                if t: st.session_state.s_t = t; st.session_state.s_d = d; st.success("✅")
        
        with st.form("gen"):
            pn = st.text_input("Product Name", value=st.session_state.s_t)
            img = st.file_uploader("Image", type=['png','jpg'])
            if st.form_submit_button("Generate"):
                if key and pn:
                    with st.spinner("AI Working..."):
                        m = get_valid_model(key)
                        res = generate_smart_script_json(key, m, pn, "", "Viral", "General", "TikTok", url, img)
                        try:
                            d = json.loads(res)
                            st.success("Success")
                            st.code(d.get('caption'), language='text')
                            for s in d.get('scenes', []): st.code(s.get('sora_prompt'), language='text')
                        except: st.error("JSON Error")

    # --- Tab 2: Advanced Video Tools (จุดที่เพิ่มใหม่) ---
    with tab_vid:
        st.header("🎬 Dynamic Watermark Remover")
        st.caption("ลบโลโก้แบบเคลื่อนที่ได้ (Moving Logo) + คุณภาพสูง")
        
        uploaded_video = st.file_uploader("Upload Video (MP4/MOV)", type=["mp4", "mov"])
        
        if uploaded_video:
            # Save Temp
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') 
            tfile.write(uploaded_video.read())
            video_path = tfile.name
            
            # Show Video
            st.video(video_path)
            
            # === ส่วนตั้งค่าการเคลื่อนไหว ===
            st.markdown("### 📍 กำหนดตำแหน่งการเบลอ (Timeline)")
            st.info("ถ้าโลโก้อยู่ที่เดิมตลอด ให้ตั้งค่าแค่ช่วงที่ 1 ก็พอ")
            
            # State สำหรับเก็บ Config
            if 'blur_segments' not in st.session_state:
                st.session_state.blur_segments = [{'start': 0, 'end': 10, 'pos': 'Top-Right'}]

            # UI สำหรับเพิ่ม/ลบ ช่วงเวลา
            cols = st.columns(3)
            with cols[0]:
                if st.button("➕ เพิ่มช่วงเวลา"):
                    st.session_state.blur_segments.append({'start': 0, 'end': 5, 'pos': 'Bottom-Right'})
            with cols[1]:
                if st.button("➖ ลบล่าสุด") and len(st.session_state.blur_segments) > 1:
                    st.session_state.blur_segments.pop()
            
            # วนลูปสร้าง Input สำหรับแต่ละช่วง
            updated_configs = []
            for idx, seg in enumerate(st.session_state.blur_segments):
                st.markdown(f"**ช่วงที่ {idx+1}**")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    s = st.number_input(f"เริ่มวินาทีที่ ({idx})", value=int(seg['start']), min_value=0, key=f"s_{idx}")
                with c2:
                    e = st.number_input(f"ถึงวินาทีที่ ({idx})", value=int(seg['end']), min_value=0, key=f"e_{idx}")
                with c3:
                    p = st.selectbox(f"ตำแหน่ง ({idx})", 
                                     ["Top-Left", "Top-Center", "Top-Right", 
                                      "Middle-Left", "Center", "Middle-Right",
                                      "Bottom-Left", "Bottom-Center", "Bottom-Right"],
                                     index=["Top-Left", "Top-Center", "Top-Right", "Middle-Left", "Center", "Middle-Right", "Bottom-Left", "Bottom-Center", "Bottom-Right"].index(seg['pos']),
                                     key=f"p_{idx}")
                updated_configs.append({'start': s, 'end': e, 'pos': p})
            
            st.session_state.blur_segments = updated_configs

            # === Quality Settings ===
            st.markdown("### ⚙️ Output Settings")
            quality = st.radio("คุณภาพไฟล์ (Bitrate)", ["Normal (เร็ว)", "High (Slow) - ชัดกริบ"], index=1)
            
            if st.button("✨ เริ่มประมวลผลวิดีโอ (Render)"):
                with st.spinner("⏳ กำลังเรนเดอร์ภาพคุณภาพสูง (High Bitrate)... อาจใช้เวลา 1-2 นาที"):
                    
                    # Call Function
                    out_path = process_video_advanced(video_path, st.session_state.blur_segments, quality)
                    
                    if out_path:
                        st.success("✅ เรนเดอร์เสร็จสิ้น!")
                        st.video(out_path)
                        
                        # Download
                        with open(out_path, "rb") as f:
                            st.download_button(
                                label="⬇️ ดาวน์โหลดวิดีโอ (High Quality)",
                                data=f,
                                file_name="cleancut_hq.mp4",
                                mime="video/mp4"
                            )
                    else:
                        st.error("เกิดข้อผิดพลาด (อย่าลืมเช็ก packages.txt ว่ามี ffmpeg ไหม)")

if st.session_state.logged_in: main_app()
else: login_screen()
