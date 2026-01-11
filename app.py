import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script Gen (Ultimate)", page_icon="🎬")

# --- เตรียมตัวแปร Session State (จำค่าข้อมูลที่ดึงมา) ---
if 'scraped_title' not in st.session_state:
    st.session_state.scraped_title = ""
if 'scraped_desc' not in st.session_state:
    st.session_state.scraped_desc = ""

# --- ฟังก์ชัน 1: ค้นหาโมเดลอัตโนมัติ (แก้ปัญหา 404) ---
def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        # 1. ลองขอรายชื่อโมเดลทั้งหมดที่มีให้ใช้
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except:
            pass # ถ้าขอรายชื่อไม่ได้ จะไปใช้ค่า Default

        # 2. ลำดับโมเดลที่อยากได้ (จากใหม่ไปเก่า)
        preferred_order = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'models/gemini-1.5-flash-001',
            'models/gemini-pro'
        ]
        
        # 3. เลือกตัวที่ดีที่สุดที่มีใน List
        for model_name in preferred_order:
            if model_name in available_models:
                return model_name
        
        # 4. ถ้าไม่เจอใน List เลย ให้เอาตัวแรกสุดที่ Google ให้มา (กันตาย)
        if available_models:
            return available_models[0]
            
        # 5. ถ้าหาไม่เจอสักตัว ให้ลองเสี่ยงดวงกับตัว Flash ล่าสุด
        return 'models/gemini-1.5-flash'
        
    except Exception as e:
        return None

# --- ฟังก์ชัน 2: ดึงข้อมูลเว็บ (ฉลาดขึ้น) ---
def scrape_web(url):
    try:
        # ปลอมตัวเป็น Browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'th-TH,th;q=0.9',
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # สูตรหาชื่อสินค้า (เรียงตามความแม่นยำ)
            # 1. หาจาก og:title (แม่นสุด)
            og_title = soup.find('meta', property='og:title')
            # 2. หาจาก twitter:title
            tw_title = soup.find('meta', name='twitter:title')
            # 3. หาจาก <title> ปกติ
            page_title = soup.title.string if soup.title else ""

            # เลือกอันที่ดีที่สุด
            final_title = ""
            if og_title and og_title.get('content'):
                final_title = og_title['content']
            elif tw_title and tw_title.get('content'):
                final_title = tw_title['content']
            else:
                final_title = page_title

            # ดึงคำอธิบาย (Description)
            og_desc = soup.find('meta', property='og:description')
            final_desc = og_desc['content'] if og_desc and og_desc.get('content') else ""
            
            # คลีนข้อมูล (ลบชื่อเว็บที่ต่อท้ายออก เช่น " | Shopee Thailand")
            clean_title = final_title.split('|')[0].strip()
            clean_title = clean_title.split(' - ')[0].strip()
            
            return clean_title, final_desc
        else:
            return None, "เข้าเว็บไม่ได้ (อาจติดกันบอท)"
    except Exception as e:
        return None, f"Error: {str(e)}"

# --- ฟังก์ชัน 3: สั่ง AI เขียนสคริปต์ ---
def generate_script(api_key, model_name, product, features, tone, url_info):
    prompt = f"""
    บทบาท: Creative Director มืออาชีพ
    งาน: เขียนสคริปต์ TikTok/Reels ขายของ ความยาว 30-45 วินาที
    ภาษา: ไทย (สไตล์ธรรมชาติ น่าสนใจ)
    
    ข้อมูลสินค้า: {product}
    ข้อมูลเพิ่มเติมจากลิงก์: {url_info}
    จุดเด่นที่ลูกค้าเน้น: {features}
    โทนของคลิป: {tone}
    
    โครงสร้างที่ต้องการ:
    1. Hook (3 วินาทีแรก): เปิดหัวให้คนหยุดดูทันที
    2. Problem: ขยี้ปัญหาที่ลูกค้าเจอ
    3. Solution: สินค้าเราช่วยยังไง + โชว์จุดเด่น
    4. Call to Action (CTA): กระตุ้นให้ซื้อเดี๋ยวนี้
    
    รูปแบบการตอบ (Output Format):
    ### ฉากที่ 1: [ชื่อฉาก]
    **🗣️ บทพูด:** [บทพูดภาษาไทย]
    **🎬 บรีฟภาพ:** [คำบรรยายฉาก มุมกล้อง การกระทำ เพื่อเอาไปทำ AI Image ต่อ]
    
    (ทำซ้ำจนครบ 4 ฉาก)
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการสร้างเนื้อหา: {str(e)}"

# ================= หน้าจอ UI หลัก =================

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("Gemini API Key", type="password")
    st.info("ขอ Key ฟรีที่: aistudio.google.com")
    
    st.divider()
    if st.button("🛠️ เช็กการเชื่อมต่อ AI"):
        if not api_key:
            st.error("ใส่ Key ก่อนครับ")
        else:
            model = get_valid_model(api_key)
            if model:
                st.success(f"เชื่อมต่อสำเร็จ! ใช้โมเดล: {model}")
            else:
                st.error("API Key ผิด หรือเชื่อมต่อไม่ได้")

st.title("🎬 AI Script Gen (Auto & Smart)")
st.caption("ดึงข้อมูลสินค้า > แก้ไขได้ > สร้างสคริปต์ขายของทันที")

# --- ส่วนที่ 1: ดึงข้อมูล (Scrape) ---
with st.container(border=True):
    st.subheader("1. ดึงข้อมูลสินค้า")
    col_url, col_btn = st.columns([3, 1])
    
    with col_url:
        url_input = st.text_input("วางลิงก์สินค้า (TikTok/Shopee/Lazada)", placeholder="https://...")
    
    with col_btn:
        st.write("") # เว้นวรรคจัดระเบียบ
        st.write("")
        scrape_clicked = st.button("🔍 ดึงข้อมูล", use_container_width=True)

    if scrape_clicked and url_input:
        with st.spinner("กำลังแกะรอยข้อมูล..."):
            title, desc = scrape_web(url_input)
            if title:
                st.session_state.scraped_title = title
                st.session_state.scraped_desc = desc
                st.success("✅ ดึงข้อมูลสำเร็จ! (ตรวจสอบด้านล่าง)")
            else:
                st.warning("⚠️ ดึงข้อมูลอัตโนมัติไม่ได้ (เว็บอาจป้องกัน) กรุณากรอกเองด้านล่างครับ")

# --- ส่วนที่ 2: กรอก/แก้ไข และสร้างสคริปต์ ---
with st.form("main_form"):
    st.subheader("2. รายละเอียดสคริปต์")
    
    # ช่องชื่อสินค้า (ดึงค่าจาก Session State มาใส่ให้)
    product_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
    
    col1, col2 = st.columns(2)
    with col1:
        tone = st.selectbox("สไตล์คลิป", ["ตลก เฮฮา", "จริงจัง ผู้เชี่ยวชาญ", "เพื่อนสาวเม้าท์มอย", "ดราม่า Storytelling"])
    with col2:
        # เอา Description ที่ดึงมาได้ มาใส่เป็น Hint หรือ Default ก็ได้
        features_default = st.session_state.scraped_desc if st.session_state.scraped_desc else ""
        features = st.text_area("จุดเด่น / ข้อมูลเพิ่มเติม", value=features_default, height=100, placeholder="ใส่จุดเด่นเอง หรือให้ระบบดึงมาให้")
        
    submitted = st.form_submit_button("🚀 สร้างสคริปต์เดี๋ยวนี้", use_container_width=True)

# --- ส่วนที่ 3: แสดงผลลัพธ์ ---
if submitted:
    if not api_key:
        st.error("❌ กรุณาใส่ API Key ที่เมนูด้านซ้ายก่อนครับ")
    elif not product_name:
        st.warning("⚠️ กรุณาระบุชื่อสินค้า")
    else:
        with st.spinner("🤖 AI กำลังทำงาน... (ค้นหาโมเดลที่ดีที่สุด)"):
            # 1. หาโมเดล
            best_model = get_valid_model(api_key)
            
            if not best_model:
                st.error("❌ หาโมเดลไม่เจอ! ลองสร้าง API Key ใหม่ หรือเช็กโค้ดอีกที")
            else:
                # 2. สร้างสคริปต์
                result = generate_script(api_key, best_model, product_name, features, tone, url_input)
                
                # แสดงผล
                st.success(f"เสร็จเรียบร้อย! (ใช้โมเดล: {best_model})")
                st.markdown("---")
                st.markdown(result)
