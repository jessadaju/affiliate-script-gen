import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Affiliate Script Gen (Auto-Fix)", page_icon="🎬")

# --- ฟังก์ชันค้นหาโมเดลอัตโนมัติ (ไม้ตาย) ---
def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # ถาม Google ว่ามีโมเดลอะไรบ้าง
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # จัดลำดับความสำคัญ (เลือกตัวใหม่ก่อน)
        preferred_order = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'models/gemini-1.0-pro',
            'models/gemini-pro'
        ]
        
        # วนหาตัวที่ตรงกับที่มีให้ใช้
        for model_name in preferred_order:
            if model_name in available_models:
                return model_name
        
        # ถ้าไม่เจอตัวที่ชอบเลย ให้เอาตัวแรกสุดที่มีมาใช้แก้ขัด
        if available_models:
            return available_models[0]
            
        return None
    except Exception as e:
        return None

# --- ฟังก์ชันดึงข้อมูลเว็บ ---
def scrape_web(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.title.string if soup.title else ""
            meta = soup.find('meta', attrs={'name': 'description'})
            desc = meta['content'] if meta else ""
            return f"Web Title: {title}\nDesc: {desc}"
        return "เข้าเว็บไม่ได้"
    except:
        return "Error Scrape"

# --- ฟังก์ชันเรียก AI ---
def generate_script(api_key, model_name, product, features, tone, url_info):
    prompt = f"""
    สินค้า: {product}
    ข้อมูลจากเว็บ: {url_info}
    จุดเด่น: {features}
    โทน: {tone}
    
    เขียนสคริปต์ TikTok ขายของ 30 วิ (มี 4 ฉาก: Hook, Problem, Solution, CTA) 
    พร้อม Visual Prompt ภาษาไทยสำหรับ AI สร้างภาพ
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# --- UI ---
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    api_key = st.text_input("Gemini API Key", type="password")
    
    # ปุ่มเช็กโมเดล (สำหรับ Debug)
    if api_key:
        st.write("---")
        if st.button("เช็กสถานะการเชื่อมต่อ"):
            valid_model = get_valid_model(api_key)
            if valid_model:
                st.success(f"✅ เชื่อมต่อสำเร็จ! ใช้โมเดล: {valid_model}")
            else:
                st.error("❌ เชื่อมต่อไม่ได้ หรือ API Key ผิด")

st.title("🎬 AI Script Gen (Auto-Model)")

with st.form("main_form"):
    url = st.text_input("🔗 Link สินค้า")
    col1, col2 = st.columns(2)
    with col1: product = st.text_input("ชื่อสินค้า")
    with col2: tone = st.selectbox("สไตล์", ["ตลก", "ทางการ", "เพื่อนเล่า", "ดราม่า"])
    feat = st.text_area("จุดเด่น")
    
    submit = st.form_submit_button("🚀 สร้างสคริปต์")

if submit:
    if not api_key:
        st.error("ใส่ API Key ก่อนครับ")
    else:
        with st.spinner("กำลังค้นหาโมเดลและสร้างสคริปต์..."):
            # 1. หาโมเดลที่ดีที่สุดอัตโนมัติ
            best_model = get_valid_model(api_key)
            
            if not best_model:
                st.error("❌ หาโมเดลไม่เจอ! กรุณาเช็ก API Key หรือสร้าง Key ใหม่")
            else:
                st.info(f"🤖 กำลังใช้สมองรุ่น: {best_model}")
                
                # 2. ดึงข้อมูลเว็บ
                web_data = ""
                if url:
                    web_data = scrape_web(url)
                
                # 3. เจนสคริปต์
                result = generate_script(api_key, best_model, product, feat, tone, web_data)
                st.success("เรียบร้อย!")
                st.markdown(result)
