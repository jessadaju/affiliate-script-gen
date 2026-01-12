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
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import random
import time

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Gen Pro", page_icon="🔒", layout="centered")

# --- 2. ระบบอีเมล (100% English to fix ASCII Error) ---
def send_verification_email(to_email, otp_code):
    """ส่งอีเมล OTP (ภาษาอังกฤษล้วน เพื่อแก้ปัญหา Error)"""
    try:
        if "email" not in st.secrets:
            st.error("Error: Email secrets not found.")
            return False

        sender_email = st.secrets["email"]["sender_email"]
        sender_password = st.secrets["email"]["sender_password"]
        
        # ✅ ใช้ภาษาอังกฤษล้วน (ปลอดภัยที่สุด)
        subject = "Verification Code (OTP) - Affiliate Gen Pro"
        body = f"""
        Hello,
        
        Your Verification Code (OTP) is: {otp_code}
        
        Please use this code to complete your registration.
        This code is valid for 5 minutes.
        
        Thank you.
        """
        
        # บังคับ Encoding เป็น UTF-8 (กันเหนียว)
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = sender_email
        msg['To'] = to_email

        # เชื่อมต่อ Server Gmail
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False

# --- 3. ระบบฐานข้อมูล (Google Sheets) ---
SHEET_NAME = "user_db"

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

def register_user_final(username, password, email):
    sheet = connect_to_gsheet()
    if not sheet: return False
    try:
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([username, hashed_pw, email, today])
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
            if row_data[1] == hashed_pw: return row_data 
        return None
    except: return None

def check_trial(start_date_str):
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        diff = (datetime.datetime.now() - start_date).days
        return diff, 3 - diff
    except: return 0, 3

# --- 4. ระบบ AI ---
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

def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    prompt_text = f"""
    Role: Professional Ad Director & Sora AI Expert.
    Task: Create a Thai video script and Sora Prompts for '{product}'.
    Data: {features} {url_info} Tone: {tone}
    
    Output Format:
    ## 📝 Viral Caption (Thai)
    [Caption 2 lines]
    [Hashtags]

    ## 🎬 Script & Sora Prompts
    (4 Scenes: Hook, Pain, Solution, CTA)
    Format per scene:
    ### Scene X: [Name]
    **🗣️ Speak (Thai):** ...
    **🎥 Sora Prompt (English - Detailed):** ```text
    [Detailed visual description]
    ```
    """
    contents = [prompt_text]
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**Vision Instruction:** Analyze the image to write accurate Sora Prompts matching the real product."
        except: pass

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    return model.generate_content(contents).text

# --- 5. UI & Logic ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None

if 'reg_stage' not in st.session_state: st.session_state.reg_stage = 1
if 'reg_otp' not in st.session_state: st.session_state.reg_otp = None
if 'reg_data' not in st.session_state: st.session_state.reg_data = {}

def login_screen():
    st.markdown("""
    <style>
        .main-card {background-color: #262730; padding: 2rem; border-radius: 10px; text-align: center; margin-bottom: 20px;}
        h1 {color: #4CAF50;}
    </style>
    <div class="main-card">
        <h1>🔒 Affiliate Gen Pro</h1>
        <p>Verified Secure Login</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", use_container_width=True):
                with st.spinner("Checking..."):
                    data = login_user(u, p)
                    if data:
                        used, left = check_trial(data[3])
                        if used > 3: st.error("Trial Expired / หมดอายุการใช้งาน")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.user_info = {"name": data[0], "email": data[2], "left": left}
                            st.rerun()
                    else: st.error("Invalid Username or Password")

    with tab2:
        if st.session_state.reg_stage == 1:
            with st.form("reg_step1"):
                new_u = st.text_input("Username *")
                new_e = st.text_input("Email (For OTP) *")
                new_p = st.text_input("Password *", type="password")
                
                if st.form_submit_button("Send OTP ->", use_container_width=True):
                    if new_u and new_e and new_p:
                        if check_user_exists(new_u):
                            st.warning("Username taken / มีคนใช้ชื่อนี้แล้ว")
                        else:
                            otp = str(random.randint(100000, 999999))
                            with st.spinner("Sending Email..."):
                                if send_verification_email(new_e, otp):
                                    st.session_state.reg_otp = otp
                                    st.session_state.reg_data = {"u": new_u, "e": new_e, "p": new_p}
                                    st.session_state.reg_stage = 2
                                    st.success("OTP Sent! Check your email.")
                                    time.sleep(1)
                                    st.rerun()
                    else:
                        st.warning("Please fill all fields")

        elif st.session_state.reg_stage == 2:
            st.info(f"OTP sent to: **{st.session_state.reg_data['e']}**")
            
            with st.form("reg_step2"):
                user_otp = st.text_input("Enter OTP Code", max_chars=6)
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_otp = st.form_submit_button("Verify & Register", use_container_width=True)
                with col2:
                    cancel = st.form_submit_button("Cancel", use_container_width=True)
                
                if submit_otp:
                    if user_otp == st.session_state.reg_otp:
                        d = st.session_state.reg_data
                        if register_user_final(d['u'], d['p'], d['e']):
                            st.success("Registration Successful!")
                            st.session_state.reg_stage = 1
                            st.session_state.reg_otp = None
                            st.session_state.reg_data = {}
                            time.sleep(2)
                            st.rerun()
                        else: st.error("Save Error")
                    else: st.error("Invalid OTP")
                
                if cancel:
                    st.session_state.reg_stage = 1
                    st.rerun()

def main_app():
    info = st.session_state.user_info
    c1, c2 = st.columns([3, 1])
    with c1: st.info(f"👤 {info['name']} | ⏳ {info['left']} Days Left")
    with c2: 
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    my_api_key = st.secrets.get("GEMINI_API_KEY")

    if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
    if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

    with st.expander("🔎 Auto Scrape (Optional)"):
        col_url, col_btn = st.columns([3, 1])
        with col_url: url = st.text_input("Product URL (TikTok/Shopee)")
        with col_btn:
            st.write(""); st.write("")
            if st.button("Scrape", use_container_width=True) and url:
                with st.spinner("Processing..."):
                    t, d = scrape_web(url)
                    if t:
                        st.session_state.scraped_title = t
                        st.session_state.scraped_desc = d
                        st.success("Done!")
                    else: st.warning("Failed")

    with st.form("gen"):
        st.subheader("1. Product Info")
        p_name = st.text_input("Product Name", value=st.session_state.scraped_title)
        img_file = st.file_uploader("Product Image (Vision)", type=['png','jpg','webp'])
        if img_file: st.image(img_file, width=150)
        
        st.subheader("2. Details")
        c1, c2 = st.columns(2)
        with c1: tone = st.selectbox("Style", ["Funny/Viral", "Cinematic", "Honest Review"])
        with c2: feat = st.text_area("Features", value=st.session_state.scraped_desc, height=100)
        
        submit = st.form_submit_button("🚀 Generate Script")
        if submit:
            if not my_api_key: st.error("API Key Not Found")
            elif not p_name and not img_file: st.warning("Name & Image required")
            else:
                with st.spinner("AI Generating..."):
                    model = get_valid_model(my_api_key)
                    if model:
                        res = generate_script(my_api_key, model, p_name, feat, tone, url, img_file)
                        st.success("Success!")
                        st.markdown(res)
                    else: st.error("AI Connection Failed")

# --- Run ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
