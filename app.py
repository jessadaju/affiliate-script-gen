import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script Gen (Pro)", page_icon="🎬")

# --- ฟังก์ชันดึงข้อมูลจากเว็บ (Web Scraper) ---
def scrape_web(url):
    try:
        # แอบปลอมตัวเป็นคนใช้งานทั่วไป (ไม่ใช่บอท)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # พยายามหาชื่อสินค้า (Title)
            title = soup.title.string if soup.title else ""
            
            # พยายามหารายละเอียด (Meta Description)
            meta = soup.find('meta', attrs={'name': 'description'})
            description = meta['content'] if meta else ""
            
            return f"ชื่อสินค้าจากเว็บ: {title}\nรายละเอียดเพิ่มเติม: {description}"
        else:
            return "ไม่สามารถเข้าถึงเว็บไซต์ได้ (อาจมีการป้องกันบอท)"
    except Exception as e:
        return f"เกิดข้อผิดพลาด: {str(e)}"

# --- ฟังก์ชันเรียก AI ---
def generate_script(api_key, product_name, features, tone, url_info=""):
    prompt = f"""
    สวมบทบาทเป็น Creative Director มือทองสำหรับ TikTok/Reels
    
    ข้อมูลสินค้า: {product_name}
    ข้อมูลเพิ่มเติมจากลิงก์: {url_info}
    จุดเด่นที่ลูกค้ากรอกมา: {features}
    โทนของคลิป: {tone}
    
    งานของคุณ:
    1. เขียนสคริปต์ขายของ 30-45 วินาที แบ่งเป็น 4 ฉาก (Hook, Problem, Solution, CTA)
    2. เขียน "Visual Prompt" (บรีฟภาพภาษาไทย) สำหรับแต่ละฉาก
    
    รูปแบบการตอบ:
    ### ฉากที่ 1: [ชื่อฉาก]
    **🗣️ บทพูด:** [ข้อความ]
    **🎬 บรีฟภาพ:** [รายละเอียดภาพ]
    
    (ทำซ้ำจนครบ 4 ฉาก)
    """
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"เกิดข้อผิดพลาด: {e}"

# --- ส่วนหน้าจอหลัก (UI) ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("ใส่ Gemini API Key", type="password")
    st.info("ขอ Key ฟรีที่: aistudio.google.com")

st.title("🎬 AI ช่วยคิดคลิป Affiliate (SaaS)")
st.caption("วางลิงก์สินค้า หรือ กรอกเองก็ได้ครบจบในที่เดียว")

# --- ส่วนฟอร์มรับข้อมูล ---
with st.form("script_form"):
    # เพิ่มช่องใส่ URL
    url_input = st.text_input("🔗 วางลิงก์สินค้า (TikTok Shop / Shopee / Lazada)", placeholder="https://...")
    
    col1, col2 = st.columns(2)
    with col1:
        product_name = st.text_input("ชื่อสินค้า (ถ้าไม่วางลิงก์)", placeholder="เช่น แก้วเก็บความเย็น")
    with col2:
        tone_select = st.selectbox("เลือกสไตล์คลิป", ["ตลก เฮฮา", "จริงจัง ผู้เชี่ยวชาญ", "ดราม่า", "เพื่อนสาวเม้าท์มอย"])
    
    features = st.text_area("จุดเด่นสินค้า (3-4 ข้อ)", placeholder="- เก็บความเย็นดีมาก\n- ไม่เป็นไอน้ำ\n- สีสวยมินิมอล")
    
    submitted = st.form_submit_button("🚀 สร้างสคริปต์เดี๋ยวนี้")

# --- ส่วนแสดงผล ---
if submitted:
    if not api_key:
        st.error("กรุณาใส่ API Key ก่อนครับ")
    else:
        with st.spinner("🤖 AI กำลังทำงาน..."):
            
            # Step 1: ถ้ามีลิงก์ ให้ลองดึงข้อมูลก่อน
            scraped_data = ""
            if url_input:
                with st.status("กำลังแกะข้อมูลจากลิงก์...", expanded=False) as status:
                    scraped_data = scrape_web(url_input)
                    status.update(label="ดึงข้อมูลเว็บเรียบร้อย!", state="complete", expanded=False)
            
            # Step 2: ส่งข้อมูลทั้งหมดให้ AI
            final_product_name = product_name if product_name else "สินค้าจากลิงก์"
            result = generate_script(api_key, final_product_name, features, tone_select, scraped_data)
            
            st.success("เสร็จเรียบร้อย!")
            st.markdown("---")
            st.markdown(result)

