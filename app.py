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
st.set_page_config(page_title="Affiliate Gen Pro (Ultimate)", page_icon="💎", layout="centered")

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
        # Structure: [User, Pass, Email, StartDate, InviteCode, PlanDays]
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

# --- 4. AI Functions (Smart JSON) ---
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
            contents[0] += "\n\n**[IMAGE ATTACHED]** Base visual prompts on this image."
        except: pass

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
    return model.generate_content(contents).text

# --- 5. Video Processing (Inpainting) ---

def extract_first_frame(video_path):
    """ดึงภาพเฟรมแรกมาเพื่อใช้ทำ Preview"""
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
    draw.rectangle([(x, y), (x + w, y + h)], outline="red", width=3)
    return img_copy

def inpaint_region_telea(frame, x, y, w, h):
    """ลบ Watermark แบบเนียน (Telea Algorithm)"""
    # 1. สร้าง Mask
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    mask[y:y+h, x:x+w] = 255
    # 2. Inpaint
    inpainted_frame = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
    return inpainted_frame

def process_video_manual_inpaint(video_path, crop_config, quality_mode="High"):
    """Process วิดีโอตามพิกัดที่ user เลือก"""
    try:
        clip = VideoFileClip(video_path)
        x, y, w_box, h_box = crop_config['x'], crop_config['y'], crop_config['w'], crop_config['h']

        def frame_processor(get_frame, t):
            frame = get_frame(t).copy() # ได้ RGB
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # แปลงเป็น BGR เพื่อทำ OpenCV
            processed_bgr = inpaint_region_telea(frame_bgr, x, y, w_box, h_box)
            frame_rgb = cv2.cvtColor(processed_bgr, cv2.COLOR_BGR2RGB) # แปลงกลับเป็น RGB
            return frame_rgb

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
    st.markdown("<h1 style='text-align:center;'>💎 Affiliate Gen Pro</h1>", unsafe_allow_html=True)
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
    
    # Tabs
    tab_gen, tab_vid = st.tabs(["🚀 AI Script Generator", "🎬 Pro Video Inpainter"])
    
    # --- Tab 1: AI (Smart JSON) ---
    with tab_gen:
        if 's_t' not in st.session_state: st.session_state.s_t = ""
        if 's_d' not in st.session_state: st.session_state.s_d = ""
        
        with st.expander("🔎 ดึงข้อมูลสินค้า"):
            url = st.text_input("URL"); 
            if st.button("Scrape") and url:
                t, d = scrape_web(url)
                if t: st.session_state.s_t = t; st.session_state.s_d = d; st.success("✅")

        with st.form("gen"):
            st.subheader("1. ข้อมูลสินค้า")
            pn = st.text_input("ชื่อสินค้า", value=st.session_state.s_t)
            img = st.file_uploader("รูปสินค้า", type=['png','jpg','webp'])
            if img: st.image(img, width=150)
            
            c1, c2 = st.columns(2)
            with c1: 
                tone = st.selectbox("โทน", ["ตลก/ไวรัล", "หรูหรา", "เพื่อนสาว", "ดราม่า"])
                platform = st.selectbox("แพลตฟอร์ม", ["TikTok", "Reels", "Shorts"])
            with c2: 
                target = st.text_input("กลุ่มเป้าหมาย", placeholder="เช่น แม่บ้าน")
                feat = st.text_area("จุดเด่น", value=st.session_state.s_d, height=100)
            
            if st.form_submit_button("⚡ สร้างสคริปต์ (ก๊อปง่าย)"):
                if key:
                    if not pn: st.warning("ใส่ชื่อสินค้า")
                    else:
                        with st.spinner("🤖 AI Thinking..."):
                            model = get_valid_model(key)
                            json_res = generate_smart_script_json(key, model, pn, feat, tone, target, platform, url, img)
                            try:
                                data = json.loads(json_res)
                                st.success("เสร็จสิ้น!")
                                st.info(f"🧠 **Strategy:** {data.get('strategy', '')}")
                                
                                st.subheader("📝 Caption")
                                st.code(f"{data.get('caption', '')}\n\n{data.get('hashtags', '')}", language='text')
                                
                                with st.expander("🎣 Hooks"):
                                    for h in data.get('hooks', []): st.code(h, language='text')

                                st.subheader("🎬 Script & Prompt")
                                for s in data.get('scenes', []):
                                    st.markdown(f"**{s.get('scene_name')}**")
                                    c1, c2 = st.columns(2)
                                    with c1: st.info(s.get('script_thai'))
                                    with c2: st.code(s.get('sora_prompt'), language="text")
                                    st.divider()
                            except: st.error("JSON Error"); st.text(json_res)

    # --- Tab 2: Pro Video Tools (Manual Inpaint) ---
    with tab_vid:
        st.header("🎬 Manual Watermark Remover")
        st.caption("ระบบลบ Watermark แบบเนียน (Telea Inpainting) พร้อมเลือกพื้นที่เอง")
        st.warning("⚠️ การลบแบบเนียนใช้เวลาประมวลผลนานกว่าปกติ (CPU Intensive)")
        
        uploaded_video = st.file_uploader("Upload Video (MP4)", type=["mp4", "mov"])
        
        if uploaded_video:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') 
            tfile.write(uploaded_video.read())
            video_path = tfile.name
            
            # 1. Preview Frame
            first_frame_img, vid_w, vid_h = extract_first_frame(video_path)
            
            if first_frame_img:
                st.markdown(f"Resolution: {vid_w}x{vid_h}")
                st.markdown("---")
                st.subheader("🎯 1. เลือกพื้นที่ (Slider)")

                # 2. Sliders
                c1, c2 = st.columns(2)
                with c1:
                    sel_x = st.slider("แนวนอน (X)", 0, vid_w, int(vid_w*0.7), key="sx")
                    sel_y = st.slider("แนวตั้ง (Y)", 0, vid_h, 20, key="sy")
                with c2:
                    sel_w = st.slider("ความกว้าง (W)", 10, vid_w - sel_x, 150, key="sw")
                    sel_h = st.slider("ความสูง (H)", 10, vid_h - sel_y, 80, key="sh")

                # 3. Show Preview
                preview_img = draw_preview_box(first_frame_img, sel_x, sel_y, sel_w, sel_h)
                st.image(preview_img, caption="พื้นที่ที่จะลบ (กรอบแดง)", use_column_width=True)
                
                st.markdown("---")
                st.subheader("⚙️ 2. ประมวลผล")
                quality = st.radio("คุณภาพ", ["Normal (เร็ว)", "High (เนียน/ช้า)"], index=1)
                
                if st.button("✨ เริ่มลบ Watermark"):
                    conf = {'x': sel_x, 'y': sel_y, 'w': sel_w, 'h': sel_h}
                    with st.spinner("⏳ กำลังเกลี่ยสี (Inpainting)... โปรดรอ..."):
                        out_path = process_video_manual_inpaint(video_path, conf, quality)
                        if out_path:
                            st.success("✅ เรียบร้อย!")
                            st.video(out_path)
                            with open(out_path, "rb") as f:
                                st.download_button("⬇️ Download", f, file_name="clean_video.mp4")
                        else: st.error("Error (Check ffmpeg)")

if st.session_state.logged_in: main_app()
else: login_screen()
