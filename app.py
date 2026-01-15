import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import time
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from moviepy.editor import VideoFileClip
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- 1. CONFIG & UI SETUP (ธีม EZRemove) ---
st.set_page_config(page_title="Magic Eraser AI", page_icon="✨", layout="wide")

# Custom CSS ให้ดูเป็น SaaS ระดับโลก
st.markdown("""
    <style>
        /* ซ่อนเมนู Streamlit เดิม */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* แต่งปุ่มกด */
        .stButton>button {
            background-color: #4F46E5;
            color: white;
            border-radius: 8px;
            font-weight: bold;
            padding: 0.5rem 2rem;
            border: none;
        }
        .stButton>button:hover {
            background-color: #4338CA;
        }
        
        /* กรอบ Canvas */
        div[data-testid="stCanvas"] {
            border: 2px solid #E5E7EB;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* หัวข้อ */
        .main-header {
            text-align: center;
            font-size: 3rem;
            font-weight: 800;
            background: -webkit-linear-gradient(45deg, #4F46E5, #EC4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .sub-header {
            text-align: center;
            color: #6B7280;
            font-size: 1.2rem;
            margin-bottom: 40px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE & AUTH (ระบบสมาชิกแบบย่อ) ---
SHEET_NAME = "user_db" # ชื่อ Google Sheet เดิมของคุณ

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

def login_user(username, password):
    sheet = connect_to_gsheet()
    if not sheet: return None # Bypass if no DB connection
    try:
        cell = sheet.find(username)
        if cell:
            row_data = sheet.row_values(cell.row)
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            if row_data[1] == hashed_pw: return row_data 
        return None
    except: return None

# --- 3. CORE LOGIC (ระบบลบ Logo) ---

def get_video_info(video_path):
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return width, height, duration

def get_frame_at_time(video_path, t):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None

def process_inpainting(video_path, mask_data, quality="Standard"):
    try:
        clip = VideoFileClip(video_path)
        
        # 1. เตรียม Mask (แปลงจาก Canvas เป็นขาวดำ)
        # Resize mask ให้เท่ากับ video จริง
        mask_resized = cv2.resize(mask_data.astype('uint8'), (clip.w, clip.h))
        alpha = mask_resized[:, :, 3]
        _, binary_mask = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
        # ขยายขอบ Mask เล็กน้อย (Dilate) เพื่อกินขอบ Logo ให้หมด
        kernel = np.ones((7,7), np.uint8) # เพิ่มขนาด Kernel เพื่อความเนียน
        binary_mask = cv2.dilate(binary_mask, kernel, iterations=3)

        # 2. ฟังก์ชันประมวลผลแต่ละเฟรม
        def process_frame(get_frame, t):
            frame = get_frame(t).copy()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # ใช้ Telea Algorithm (Fast & Good for small logos)
            # หรือ Navier-Stokes (cv2.INPAINT_NS) ลองเปลี่ยนได้
            inpainted = cv2.inpaint(frame_bgr, binary_mask, 5, cv2.INPAINT_TELEA)
            
            return cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)

        # 3. Render
        final_clip = clip.fl(process_frame)
        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        
        bitrate = "8000k" if quality == "High Quality" else "3000k"
        preset = "medium" if quality == "High Quality" else "ultrafast"

        final_clip.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac",
            bitrate=bitrate, 
            preset=preset, 
            fps=clip.fps,
            logger=None # ปิด log รกๆ
        )
        
        clip.close()
        return output_path
    except Exception as e:
        return None

# --- 4. APP UI ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

def login_page():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div style='text-align:center; margin-top:50px;'><h1>🔐 Login</h1></div>", unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Access Tool", use_container_width=True):
                if login_user(u, p):
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")

def main_tool():
    # Header
    st.markdown('<div class="main-header">Magic Video Eraser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Remove logos, watermarks, and objects from your videos instantly.</div>', unsafe_allow_html=True)

    # Main Layout
    c_main = st.container()
    
    with c_main:
        # Step 1: Upload
        uploaded_file = st.file_uploader("📂 Upload Video (MP4, MOV)", type=["mp4", "mov"])
        
        if uploaded_file:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_file.read())
            video_path = tfile.name
            
            # Get Info
            w, h, duration = get_video_info(video_path)
            
            # --- UI Zone ---
            col_tool, col_preview = st.columns([2, 1])
            
            # State for timeline
            if 'time_pos' not in st.session_state: st.session_state.time_pos = 0.0
            
            with col_tool:
                st.markdown("### 🖌️ 1. Paint over the object")
                
                # Timeline Control
                st.session_state.time_pos = st.slider("Select Frame to Paint", 0.0, float(duration), st.session_state.time_pos, 0.1)
                
                # Get Frame for Canvas
                frame_img = get_frame_at_time(video_path, st.session_state.time_pos)
                
                if frame_img is not None:
                    # Canvas Size Logic (Fit width, maintain aspect ratio)
                    canv_width = 700
                    canv_height = int(canv_width * (h / w))
                    
                    pil_img = Image.fromarray(frame_img).resize((canv_width, canv_height))
                    
                    # Canvas
                    canvas = st_canvas(
                        fill_color="rgba(255, 0, 0, 0.6)", # สีแดงโปร่งแสงแบบ EZRemove
                        stroke_width=st.slider("Brush Size", 5, 100, 30),
                        stroke_color="rgba(255, 0, 0, 1)",
                        background_image=pil_img,
                        update_streamlit=True,
                        height=canv_height,
                        width=canv_width,
                        drawing_mode="freedraw",
                        key="eraser_canvas"
                    )
            
            with col_preview:
                st.markdown("### ⚙️ 2. Settings")
                quality = st.radio("Output Quality", ["Standard (Fast)", "High Quality (Slow)"])
                
                st.info(f"📹 Resolution: {w}x{h}\n⏱️ Duration: {duration:.1f}s")
                
                st.markdown("---")
                if st.button("✨ ERASE OBJECT NOW", use_container_width=True):
                    if canvas.image_data is not None and np.sum(canvas.image_data[:,:,3]) > 0:
                        with st.spinner("🪄 Magic is happening... (This may take a while)"):
                            out_path = process_inpainting(video_path, canvas.image_data, quality)
                            
                            if out_path:
                                st.success("✅ Done!")
                                st.video(out_path)
                                with open(out_path, "rb") as f:
                                    st.download_button(
                                        "⬇️ Download Result", 
                                        f, 
                                        file_name="magic_erased.mp4",
                                        use_container_width=True
                                    )
                    else:
                        st.warning("Please paint over the logo first!")

# --- APP FLOW ---
if st.session_state.logged_in:
    main_tool()
else:
    login_page()
