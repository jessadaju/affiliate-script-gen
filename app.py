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
from streamlit_drawable_canvas import st_canvas

# --- 1. ตั้งค่าหน้าเว็บ (Layout Wide เพื่อให้วาดรูปได้กว้างขึ้น) ---
st.set_page_config(page_title="Affiliate Gen Pro (Precision)", page_icon="🎯", layout="wide")

# 🎨 CSS เสริม: บังคับให้ Canvas แสดงผลเต็มขนาดจริงและมี Scrollbar ถ้าล้นจอ
st.markdown("""
    <style>
        .stCanvas {
            overflow: auto; /* ให้มี scrollbar ถ้ารูปใหญ่กว่าจอ */
            border: 2px solid #FF4B4B; /* กรอบสีแดงเพื่อให้รู้เขตพื้นที่วาด */
        }
        /* ปรับให้ container ของ canvas ขยายเต็มที่ */
        [data-testid="stExpander"] details {
            overflow: auto;
        }
    </style>
""", unsafe_allow_html=True)


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

def check_status(start_date_str, plan_days_str):
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        plan_days = int(plan_days_str)
        now = datetime.datetime.now()
        diff = (now - start_date).days
        remaining = plan_days - diff
        return diff, remaining 
    except: return 0, 0

# --- 4. AI Functions ---
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
    **IMPORTANT:** Return ONLY valid JSON:
    {{
      "strategy": "...", "hooks": ["..."], "caption": "...", "hashtags": "...",
      "scenes": [ {{ "scene_name": "...", "script_thai": "...", "sora_prompt": "..." }} ]
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

# --- 5. Video Processing (Mask Inpainting) ---

def extract_frame_at_time(video_path, seconds):
    """ดึงภาพเฟรม ณ วินาทีที่กำหนด"""
    try:
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ret, frame = cap.read()
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS))
        
        cap.release()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb), width, height, duration
        return None, 0, 0, 0
    except: return None, 0, 0, 0

def process_video_with_mask(video_path, mask_image_data, quality_mode="High"):
    """รับ Mask จาก Canvas แล้ว Inpaint วิดีโอ"""
    try:
        clip = VideoFileClip(video_path)
        
        # Resize Mask ให้เท่ากับขนาดวิดีโอ (สำคัญมาก: เพื่อให้แน่ใจว่า pixel ตรงกัน)
        mask_resized = cv2.resize(mask_image_data.astype('uint8'), (clip.w, clip.h))
        
        alpha_channel = mask_resized[:, :, 3] 
        _, binary_mask = cv2.threshold(alpha_channel, 1, 255, cv2.THRESH_BINARY)
        # ขยายขอบเขต Mask เล็กน้อยเพื่อความเนียน
        kernel = np.ones((5,5), np.uint8)
        binary_mask = cv2.dilate(binary_mask, kernel, iterations=2)

        def frame_processor(get_frame, t):
            frame = get_frame(t).copy()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            # ใช้ Telea Inpainting ที่ตำแหน่งแม่นยำจาก Mask
            inpainted = cv2.inpaint(frame_bgr, binary_mask, 3, cv2.INPAINT_TELEA)
            return cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)

        final_clip = clip.fl(frame_processor)
        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        
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
if 'current_time' not in st.session_state: st.session_state.current_time = 0.0

def login_screen():
    st.markdown("<h1 style='text-align:center;'>🎯 Affiliate Gen Pro</h1>", unsafe_allow_html=True)
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
    if i.get('exp'): st.error("หมดอายุการใช้งาน"); return

    st.info(f"👤 {i['name']} | ⏳ {i['left']} Days Left")
    if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
    
    key = st.secrets.get("GEMINI_API_KEY")
    
    tab_gen, tab_vid = st.tabs(["🚀 AI Script", "🎨 Pen Tool (Precision Mode)"])
    
    # --- Tab 1: AI ---
    with tab_gen:
        # (ส่วน AI Script เหมือนเดิม ย่อไว้)
        st.write("AI Script Generator Section...")

    # --- Tab 2: Pen Tool (เน้นความแม่นยำ) ---
    with tab_vid:
        st.header("🎨 Manual Pen Remover (Precision Mode)")
        st.caption("วาด Mask ทับ Watermark บนเฟรมความละเอียดจริง (1:1 pixel accurate)")
        
        uploaded_video = st.file_uploader("Upload Video", type=["mp4", "mov"])
        
        if uploaded_video:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') 
            tfile.write(uploaded_video.read())
            video_path = tfile.name
            
            # Extract info
            _, vid_w, vid_h, vid_dur = extract_frame_at_time(video_path, 0)
            
            # --- 1. Navigation ---
            st.markdown("### 1️⃣ เลือกเฟรมที่จะวาด (Timeline)")
            c_nav1, c_nav2, c_nav3 = st.columns([1, 4, 1])
            with c_nav1:
                if st.button("⏪ -1s"): st.session_state.current_time = max(0, st.session_state.current_time - 1)
            with c_nav2:
                time_sel = st.slider("Time (sec)", 0.0, float(vid_dur), st.session_state.current_time, 0.1)
                st.session_state.current_time = time_sel
            with c_nav3:
                if st.button("⏩ +1s"): st.session_state.current_time = min(vid_dur, st.session_state.current_time + 1)
            
            # --- 2. Canvas Mode Selection ---
            st.markdown("### 2️⃣ วาด Mask (ระบายสีแดง)")
            # ตั้ง Default เป็น Original เพื่อความแม่นยำตามที่ user ต้องการ
            view_mode = st.radio("โหมดการวาด:", ["Original 1:1 (แม่นยำที่สุด - แนะนำ)", "Fit Screen (ย่อให้พอดีจอ)"], index=0, horizontal=True)
            
            frame_img, _, _, _ = extract_frame_at_time(video_path, st.session_state.current_time)
            
            if frame_img:
                # คำนวณขนาด Canvas ตามโหมดที่เลือก
                if view_mode == "Original 1:1 (แม่นยำที่สุด - แนะนำ)":
                    canvas_width = vid_w
                    canvas_height = vid_h
                    frame_for_canvas = frame_img # ไม่ย่อ ส่งภาพเต็มไปเลย
                    st.info(f"🔍 คุณกำลังวาดบนความละเอียดจริง: {vid_w}x{vid_h} พิกเซล (ตำแหน่งตรงเป๊ะ 100%)")
                    st.warning("👉 หากภาพใหญ่เกินจอ ให้ใช้ Scrollbar ด้านล่าง/ด้านขวา เพื่อเลื่อนหาตำแหน่ง Watermark ครับ")
                else:
                    # โหมดย่อ (Fit Screen)
                    canvas_width = 800
                    aspect_ratio = vid_h / vid_w
                    canvas_height = int(canvas_width * aspect_ratio)
                    frame_for_canvas = frame_img.resize((canvas_width, canvas_height))
                    st.info(f"📱 โหมดย่อส่วน: {canvas_width}x{canvas_height} (ดูภาพรวมง่าย แต่อาจคลาดเคลื่อนเล็กน้อย)")

                # Canvas Container (มีกรอบสีแดง)
                with st.container(border=True):
                     # Canvas
                    canvas_result = st_canvas(
                        fill_color="rgba(255, 0, 0, 0.5)", # สีแดงโปร่งแสง
                        stroke_width=st.slider("ขนาดหัวปากกา", 5, 150, 30),
                        stroke_color="rgba(255, 0, 0, 1)",
                        background_image=frame_for_canvas,
                        update_streamlit=True,
                        height=canvas_height,
                        width=canvas_width,
                        drawing_mode="freedraw",
                        key=f"canvas_{view_mode}", # เปลี่ยน key เพื่อให้ canvas รีเซ็ตเมื่อเปลี่ยนโหมด
                    )
                
                st.markdown("---")
                st.markdown("### 3️⃣ ประมวลผล")
                quality = st.radio("Quality", ["Normal", "High (Slow - เนียนกว่า)"], index=1)
                
                if st.button("✨ Start Inpainting (เริ่มลบ)"):
                    if canvas_result.image_data is not None:
                        # ตรวจสอบว่ามีการวาดเกิดขึ้นจริงหรือไม่ (เช็ค Alpha channel)
                        if np.sum(canvas_result.image_data[:, :, 3]) == 0:
                             st.warning("⚠️ คุณยังไม่ได้ระบายสีแดงลงบนภาพเลยครับ กรุณาวาดทับ Watermark ก่อน")
                        else:
                            with st.spinner("⏳ กำลังประมวลผล... (Inpainting ทีละเฟรม อาจใช้เวลานาน)"):
                                # ฟังก์ชันนี้จะจัดการ Resize Mask ให้ตรงกับวิดีโอต้นฉบับให้อัตโนมัติ
                                out_path = process_video_with_mask(video_path, canvas_result.image_data, quality)
                                if out_path:
                                    st.success("✅ เสร็จสิ้น!")
                                    st.subheader("📺 ผลลัพธ์ (Processed Video)")
                                    st.video(out_path)
                                    with open(out_path, "rb") as f:
                                        st.download_button("⬇️ Download Video", f, file_name="clean_video.mp4")
                                else: st.error("Error Processing (Memory/FFmpeg issue)")
                    else: st.warning("Please draw mask first")

if st.session_state.logged_in: main_app()
else: login_screen()
