import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image, ImageDraw
import datetime
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import os
import tempfile
from moviepy.editor import VideoFileClip
import cv2
import numpy as np

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Gen Pro (Pro Video Tools)", page_icon="🎬", layout="centered")

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
        {{ "scene_name": "Scene 2", "script_thai": "...", "sora_prompt": "..." }}
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

# --- 5. Pro Video Processing (Manual Inpaint) ---

def extract_first_frame(video_path):
    """ดึงภาพเฟรมแรกมาเพื่อใช้ทำ Preview ในการเลือกพื้นที่"""
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if ret:
            # แปลง BGR (OpenCV) เป็น RGB (PIL/Streamlit)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb), frame.shape[1], frame.shape[0] # img, w, h
        return None, 0, 0
    except: return None, 0, 0

def draw_preview_box(image, x, y, w, h):
    """วาดกรอบสี่เหลี่ยมสีแดงบนภาพ Preview"""
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    # วาดกรอบสีแดง หนา 3px
    draw.rectangle([(x, y), (x + w, y + h)], outline="red", width=3)
    return img_copy

def inpaint_region_telea(frame, x, y, w, h):
    """
    🔥 หัวใจสำคัญ: ฟังก์ชันลบ Watermark แบบเนียน (Telea Algorithm)
    ใช้ OpenCV Inpaint แทนการ Pixelate
    """
    # 1. สร้าง Mask สีดำทั้งภาพ
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    # 2. เจาะรูสีขาวตรงพื้นที่สี่เหลี่ยมที่เราเลือก (ROI)
    mask[y:y+h, x:x+w] = 255
    
    # 3. สั่ง OpenCV ให้ถมดำรูนั้น โดยอิงจากสีรอบข้าง (Radius 3px)
    # cv2.INPAINT_TELEA คืออัลกอริทึมที่เนียนและเร็วที่สุดสำหรับ CPU
    inpainted_frame = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
    return inpainted_frame

def process_video_manual_inpaint(video_path, crop_config, quality_mode="High"):
    """Process วิดีโอตามพิกัดที่ user เลือกมา"""
    try:
        clip = VideoFileClip(video_path)
        
        # ดึงค่า Config พื้นที่
        x, y, w_box, h_box = crop_config['x'], crop_config['y'], crop_config['w'], crop_config['h']

        # ฟังก์ชันที่จะรันทุกเฟรม
        def frame_processor(get_frame, t):
            frame = get_frame(t).copy() # ได้เฟรมเป็น RGB
            
            # OpenCV ต้องการ BGR ในการประมวลผล
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # ทำ Inpainting
            processed_bgr = inpaint_region_telea(frame_bgr, x, y, w_box, h_box)
            
            # แปลงกลับเป็น RGB เพื่อส่งให้ MoviePy
            frame_rgb = cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB)
            return frame_rgb

        # สร้าง Clip ใหม่
        final_clip = clip.fl(frame_processor)
        
        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        
        # Quality Settings
        if quality_mode == "High (Slow)":
            bitrate, preset = "8000k", "medium"
        else:
            bitrate, preset = "3000k", "ultrafast"

        final_clip.write_videofile(
            output_path, codec="libx264", audio_codec="aac",
            bitrate=bitrate, preset=preset, fps=clip.fps
        )
        
        clip.close()
        return output_path
    except Exception as e:
        print(f"Error: {e}")
        return None

# --- 6. UI Logic ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

def login_screen():
    # ... (โค้ด Login เดิม ย่อไว้เพื่อความกระชับ) ...
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
                if c in VALID_INVITE_CODES and not check_user_exists(nu):
                   if register_user(nu, np, ne, c): st.success("Success!"); time.sleep(1); st.rerun()
                else: st.error("Error")

def main_app():
    i = st.session_state.user_info
    # ... (Admin & Renewal checks เดิม) ...
    if i.get('exp'): st.error("Expired"); return

    st.info(f"👤 {i['name']} | ⏳ {i['left']} Days Left")
    if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
    
    key = st.secrets.get("GEMINI_API_KEY")
    
    tab_gen, tab_vid = st.tabs(["🚀 AI Script Generator", "🎬 Pro Video Inpainter"])
    
    # --- Tab 1: AI (ย่อไว้) ---
    with tab_gen:
        st.write("(AI Generator section is here...)")

    # --- Tab 2: Pro Video Inpainter (New!) ---
    with tab_vid:
        st.header("🎬 Manual Watermark Remover (Smooth Inpaint)")
        st.caption("ลบโลโก้แบบเนียนโดยใช้เทคโนโลยีเกลี่ยสี (Telea Inpainting) และเลือกพื้นที่เอง")
        st.warning("⚠️ วิธีนี้ใช้ CPU ประมวลผลหนักมาก วิดีโอ 10 วินาทีอาจใช้เวลา 1-3 นาที กรุณารออย่างใจเย็น")
        
        uploaded_video = st.file_uploader("Upload Video (MP4/MOV)", type=["mp4", "mov"])
        
        if uploaded_video:
            # Save Temp & Get Info
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') 
            tfile.write(uploaded_video.read())
            video_path = tfile.name
            
            # 1. ดึงเฟรมแรกมาโชว์
            first_frame_img, vid_w, vid_h = extract_first_frame(video_path)
            
            if first_frame_img:
                st.markdown(f"**Video Resolution:** {vid_w} x {vid_h}")
                st.markdown("---")
                st.subheader("🎯 1. กำหนดพื้นที่ Watermark")
                st.caption("ปรับ Slider ด้านล่างให้กรอบสีแดงครอบทับโลโก้พอดี")

                # 2. สร้าง Slider สำหรับเลือกพื้นที่ (Manual Selection)
                col_pos, col_size = st.columns(2)
                with col_pos:
                    st.markdown("**ตำแหน่งเริ่มต้น (มุมซ้ายบน)**")
                    # Default ให้อยู่มุมขวาบน
                    default_x = int(vid_w * 0.7)
                    sel_x = st.slider("แนวนอน (X)", 0, vid_w, default_x, key="sx")
                    sel_y = st.slider("แนวตั้ง (Y)", 0, vid_h, 20, key="sy")
                with col_size:
                    st.markdown("**ขนาดกรอบ**")
                    sel_w = st.slider("ความกว้าง (Width)", 10, vid_w - sel_x, 150, key="sw")
                    sel_h = st.slider("ความสูง (Height)", 10, vid_h - sel_y, 80, key="sh")

                # 3. โชว์ภาพ Preview พร้อมกรอบแดง
                preview_img = draw_preview_box(first_frame_img, sel_x, sel_y, sel_w, sel_h)
                st.image(preview_img, caption="Preview พื้นที่จะถูกลบ (กรอบแดง)", use_column_width=True)
                
                st.markdown("---")
                st.subheader("⚙️ 2. ตั้งค่าและเริ่มประมวลผล")
                quality = st.radio("คุณภาพไฟล์ Output", ["Normal (เร็วกว่านิดหน่อย)", "High (ช้ามาก แต่ชัด)"], index=1)
                
                if st.button("✨ เริ่มลบ Watermark (Inpaint)"):
                    config = {'x': sel_x, 'y': sel_y, 'w': sel_w, 'h': sel_h}
                    
                    with st.spinner("⏳ กำลังเกลี่ยสีทีละเฟรม... ขั้นตอนนี้ใช้เวลานาน ห้ามปิดหน้าต่าง..."):
                        # Call Process Function
                        out_path = process_video_manual_inpaint(video_path, config, quality)
                        
                        if out_path:
                            st.success("✅ เสร็จสมบูรณ์! เนียนกริบ")
                            st.video(out_path)
                            with open(out_path, "rb") as f:
                                st.download_button("⬇️ ดาวน์โหลดวิดีโอ", f, file_name="inpainted_video.mp4")
                        else:
                            st.error("เกิดข้อผิดพลาด (Memory อาจไม่พอ หรือขาด ffmpeg)")
            else:
                st.error("ไม่สามารถอ่านไฟล์วิดีโอได้")

if st.session_state.logged_in: main_app()
else: login_screen()
