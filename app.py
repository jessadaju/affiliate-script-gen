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
from moviepy.editor import VideoFileClip
import cv2
import numpy as np
from streamlit_drawable_canvas import st_canvas

# --- 1. UI CONFIGURATION ---
st.set_page_config(page_title="Affiliate Gen Pro (All-in-One)", page_icon="💎", layout="wide")

# Custom CSS: ให้ดูทันสมัยและจัดการ Canvas
st.markdown("""
    <style>
        .stButton>button {
            background-color: #4F46E5;
            color: white;
            border-radius: 8px;
            font-weight: bold;
            border: none;
            height: 3em;
        }
        .stButton>button:hover { background-color: #4338CA; }
        
        div[data-testid="stCanvas"] {
            border: 2px solid #E5E7EB;
            border-radius: 10px;
        }
        
        h1, h2, h3 { color: #1F2937; }
        .big-font { font-size: 20px !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONFIG & AUTH ---
VALID_INVITE_CODES = ["VIP2024", "EARLYBIRD", "ADMIN"]
SHEET_NAME = "user_db"
ADMIN_USERNAME = "admin"

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
        cell = sheet.find(username)
        if cell:
            row_data = sheet.row_values(cell.row)
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            if row_data[1] == hashed_pw:
                if len(row_data) < 6: row_data.append("3")
                return row_data 
        return None
    except: return None

# --- 3. AI LOGIC (SCRIPT & PROMPTS) ---

def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # Use Flash for speed or Pro for logic
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
    # Prompt ที่สั่งให้ AI สร้าง Script + Sora Prompts แบบละเอียด
    prompt_text = f"""
    Act as a World-Class Creative Director & AI Video Expert.
    Task: Create a high-converting video script for '{product}'.
    
    Context:
    - Platform: {platform}
    - Target Audience: {target_audience}
    - Tone: {tone}
    - Product Data: {features} {url_info}
    
    Visual Instructions for Sora Prompts:
    - Describe lighting (e.g., Cinematic, Soft box, Golden hour).
    - Describe camera movement (e.g., Dolly in, Slow pan, Macro shot).
    - Describe texture and materials clearly.
    
    **IMPORTANT:** Return ONLY valid JSON with this exact structure:
    {{
      "strategy": "Briefly explain why this angle works",
      "hooks": ["Hook Option 1 (Stop scrolling)", "Hook Option 2 (Problem-Solution)", "Hook Option 3 (Shocking)"],
      "caption": "Viral caption with emojis",
      "hashtags": "#tag1 #tag2 #tag3",
      "scenes": [
        {{
          "scene_name": "Scene 1: Hook (0-3s)",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English prompt for Sora/Kling: [Subject] + [Action] + [Environment] + [Lighting/Camera]"
        }},
        {{
          "scene_name": "Scene 2: Problem/Demo (3-10s)",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English prompt..."
        }},
        {{
          "scene_name": "Scene 3: Solution/Benefit (10-20s)",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English prompt..."
        }},
        {{
          "scene_name": "Scene 4: CTA (20-30s)",
          "script_thai": "Thai spoken script...",
          "sora_prompt": "English prompt..."
        }}
      ]
    }}
    """
    
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**[IMAGE ATTACHED]** Analyze this image to create accurate visual prompts."
        except: pass

    genai.configure(api_key=api_key)
    # บังคับ JSON Mode
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
    return model.generate_content(contents).text

# --- 4. VIDEO LOGIC (INPAINTING) ---

def get_video_frame(video_path, t):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ret, frame = cap.read()
    cap.release()
    if ret: return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None

def get_video_duration(video_path):
    clip = VideoFileClip(video_path)
    dur = clip.duration
    clip.close()
    return dur

def process_inpainting(video_path, mask_data, quality="Standard"):
    try:
        clip = VideoFileClip(video_path)
        
        # Resize mask to match video dimensions
        mask_resized = cv2.resize(mask_data.astype('uint8'), (clip.w, clip.h))
        alpha = mask_resized[:, :, 3]
        _, binary_mask = cv2.threshold(alpha, 1, 255, cv2.THRESH_BINARY)
        # Dilate mask to cover edges
        kernel = np.ones((7,7), np.uint8)
        binary_mask = cv2.dilate(binary_mask, kernel, iterations=3)

        def process_frame(get_frame, t):
            frame = get_frame(t).copy()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            # Telea Inpainting
            inpainted = cv2.inpaint(frame_bgr, binary_mask, 5, cv2.INPAINT_TELEA)
            return cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)

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
            logger=None
        )
        clip.close()
        return output_path
    except Exception as e: return None

# --- 5. APP UI ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = {}

def login_screen():
    st.markdown("<h1 style='text-align:center;'>💎 Affiliate Gen Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                d = login_user(u, p)
                if d:
                    st.session_state.logged_in = True
                    st.session_state.user_info = {"name": d[0], "left": d[5] if len(d)>5 else "3"}
                    st.rerun()
                else: st.error("Login Failed")
    with t2:
        with st.form("reg_form"):
            nu = st.text_input("Username"); ne = st.text_input("Email"); np = st.text_input("Password", type="password"); c = st.text_input("Invite Code")
            if st.form_submit_button("Register"):
                if c in VALID_INVITE_CODES and not check_user_exists(nu):
                    if register_user(nu, np, ne, c): st.success("Success! Login now."); time.sleep(1); st.rerun()
                else: st.error("Invalid Code or Username Taken")

def main_app():
    # Sidebar / Header
    c1, c2 = st.columns([3, 1])
    with c1: st.info(f"👋 Welcome, {st.session_state.user_info.get('name')} | Mode: All-in-One")
    with c2: 
        if st.button("Logout"): 
            st.session_state.logged_in = False
            st.rerun()

    key = st.secrets.get("GEMINI_API_KEY")

    # === MAIN TABS ===
    tab_ai, tab_video = st.tabs(["🚀 AI Script & Prompts", "✨ Magic Video Eraser"])

    # ----------------------------------------------------
    # TAB 1: AI SCRIPT GENERATOR (The Original Feature)
    # ----------------------------------------------------
    with tab_ai:
        st.markdown("### 🧠 Generate Scripts & Sora Prompts")
        
        # State for Scraper
        if 's_title' not in st.session_state: st.session_state.s_title = ""
        if 's_desc' not in st.session_state: st.session_state.s_desc = ""

        with st.expander("🔎 Import from URL (Shopee/TikTok/Lazada)"):
            url = st.text_input("Product URL")
            if st.button("Scrape Data") and url:
                t, d = scrape_web(url)
                if t:
                    st.session_state.s_title = t
                    st.session_state.s_desc = d
                    st.success("Data Imported!")
                else: st.error("Could not scrape data")

        with st.form("ai_gen_form"):
            col1, col2 = st.columns(2)
            with col1:
                p_name = st.text_input("Product Name", value=st.session_state.s_title)
                img_file = st.file_uploader("Reference Image (for Vision)", type=['png','jpg','webp'])
                tone = st.selectbox("Tone / Style", ["Viral/Funny", "Luxury/Cinematic", "Friendly/Review", "Problem-Solution"])
            
            with col2:
                target = st.text_input("Target Audience", placeholder="e.g. Office workers, Students")
                platform = st.selectbox("Platform", ["TikTok", "Instagram Reels", "YouTube Shorts"])
                features = st.text_area("Key Features / Benefits", value=st.session_state.s_desc, height=130)

            if st.form_submit_button("⚡ Generate Script"):
                if not key: st.error("API Key missing in secrets")
                elif not p_name: st.warning("Please enter product name")
                else:
                    with st.spinner("🤖 AI is crafting your script & prompts..."):
                        model = get_valid_model(key)
                        json_result = generate_smart_script_json(key, model, p_name, features, tone, target, platform, url, img_file)
                        
                        try:
                            data = json.loads(json_result)
                            st.success("Generation Complete!")
                            st.divider()
                            
                            # 1. Strategy
                            st.info(f"🧠 **Strategy:** {data.get('strategy', 'N/A')}")
                            
                            # 2. Hooks
                            with st.expander("🎣 3 Viral Hooks (Click to see)", expanded=True):
                                for h in data.get('hooks', []): st.code(h, language="text")
                            
                            # 3. Caption
                            st.subheader("📝 Caption & Hashtags")
                            st.code(f"{data.get('caption', '')}\n\n{data.get('hashtags', '')}", language="text")
                            
                            # 4. Scenes (Copy Button Enabled)
                            st.subheader("🎬 Video Script & Sora Prompts")
                            for scene in data.get('scenes', []):
                                with st.container():
                                    st.markdown(f"**{scene.get('scene_name')}**")
                                    c_thai, c_eng = st.columns(2)
                                    with c_thai: 
                                        st.caption("🇹🇭 Script (Thai)")
                                        st.info(scene.get('script_thai'))
                                    with c_eng:
                                        st.caption("🇺🇸 Sora/Kling Prompt (English)")
                                        st.code(scene.get('sora_prompt'), language="text")
                                    st.divider()
                        except:
                            st.error("Error parsing AI response. Please try again.")

    # ----------------------------------------------------
    # TAB 2: MAGIC VIDEO ERASER (The New Feature)
    # ----------------------------------------------------
    with tab_video:
        st.markdown("### ✨ Remove Objects/Watermarks")
        
        uploaded_video = st.file_uploader("Upload Video (MP4/MOV)", type=["mp4", "mov"])
        
        if uploaded_video:
            # Save Temp
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(uploaded_video.read())
            video_path = tfile.name
            
            # Get Info
            duration = get_video_duration(video_path)
            
            # Layout
            col_tool, col_preview = st.columns([2, 1])
            
            # State for timeline
            if 'vid_time' not in st.session_state: st.session_state.vid_time = 0.0
            
            with col_tool:
                st.markdown("#### 🖌️ 1. Paint area to remove")
                
                # Timeline
                st.session_state.vid_time = st.slider("Select Frame", 0.0, float(duration), st.session_state.vid_time, 0.1)
                
                # Get Frame
                frame_img = get_video_frame(video_path, st.session_state.vid_time)
                
                if frame_img is not None:
                    # Logic to fit canvas in screen
                    h, w, _ = frame_img.shape
                    canv_width = 700
                    canv_height = int(canv_width * (h / w))
                    
                    # Resize for display
                    pil_img = Image.fromarray(frame_img).resize((canv_width, canv_height))
                    
                    canvas = st_canvas(
                        fill_color="rgba(255, 0, 0, 0.5)",
                        stroke_width=st.slider("Brush Size", 5, 100, 30),
                        stroke_color="rgba(255, 0, 0, 1)",
                        background_image=pil_img,
                        update_streamlit=True,
                        height=canv_height,
                        width=canv_width,
                        drawing_mode="freedraw",
                        key="video_eraser_canvas"
                    )
            
            with col_preview:
                st.markdown("#### ⚙️ 2. Settings")
                quality = st.radio("Output Quality", ["Standard (Fast)", "High Quality (Slow)"])
                
                st.info("💡 Paint over the watermark/logo in red.")
                st.warning("Processing takes time. Please wait.")
                
                if st.button("✨ Start Magic Eraser", use_container_width=True):
                    if canvas.image_data is not None and np.sum(canvas.image_data[:,:,3]) > 0:
                        with st.spinner("⏳ Inpainting..."):
                            out_path = process_inpainting(video_path, canvas.image_data, quality)
                            if out_path:
                                st.success("✅ Done!")
                                st.video(out_path)
                                with open(out_path, "rb") as f:
                                    st.download_button("⬇️ Download", f, file_name="clean.mp4", use_container_width=True)
                            else: st.error("Error processing video")
                    else: st.warning("Please draw mask first")

# --- APP ENTRY POINT ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
