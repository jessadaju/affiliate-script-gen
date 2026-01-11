import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image # เพิ่มตัวจัดการรูปภาพ

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script Gen (Vision Edition)", page_icon="👁️")

# --- Session State ---
if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

# --- ฟังก์ชันค้นหาโมเดล (คงเดิม) ---
def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        available_models = []
        try:
            for m in genai.list_models():
                # เช็กว่าโมเดลรองรับการสร้างเนื้อหาหรือไม่
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except: pass
        
        # เน้นโมเดล 1.5 เพราะรองรับการดูรูปภาพได้ดี
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        for model_name in preferred_order:
            if model_name in available_models: return model_name
        
        # กันตาย
        return available_models[0] if available_models else 'models/gemini-1.5-flash'
    except: return None

# --- ฟังก์ชันดึงข้อมูล (คงเดิม) ---
def scrape_web(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            final_title, final_desc = "", ""

            # Tech 1: JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if '@type' in data and data['@type'] == 'Product':
                        final_title = data.get('name', '')
                        final_desc = data.get('description', '')
                        break
                    if '@type' in data and data['@type'] == 'BreadcrumbList':
                        if 'itemListElement' in data:
                            final_title = data['itemListElement'][-1]['item']['name']
                except: continue

            # Tech 2: Open Graph
            if not final_title:
                og_title = soup.find('meta', property='og:title')
                if og_title: final_title = og_title.get('content', '')
            if not final_desc:
                og_desc = soup.find('meta', property='og:description')
                if og_desc: final_desc = og_desc.get('content', '')

            # Tech 3: Page Title
            if not final_title and soup.title: final_title = soup.title.string

            clean_title = final_title.split('|')[0].split(' - ')[0].strip()
            if clean_title: return clean_title, final_desc
            else: return None, "เว็บป้องกันหนาแน่น ไม่พบข้อมูล"
        else: return None, f"เข้าเว็บไม่ได้ (Status: {response.status_code})"
    except Exception as e: return None, f"Error: {str(e)}"

# --- ฟังก์ชันสร้างสคริปต์ (อัปเกรดใหม่: รองรับรูปภาพ!) ---
def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    
    # คำสั่งหลัก (Text Prompt)
    prompt_text = f"""
    บทบาท: Creative Director มืออาชีพสำหรับ TikTok/Reels
    งาน: เขียนสคริปต์ขายของ 30-45 วินาที และ Visual Prompt
    
    ข้อมูลสินค้า (จากผู้ใช้): {product}
    ข้อมูลเพิ่มเติม (จากลิงก์): {url_info}
    จุดเด่นที่เน้น: {features}
    โทน: {tone}
    """
    
    # เตรียมข้อมูลส่งให้ AI (เริ่มจากข้อความก่อน)
    contents = [prompt_text]

    # ถ้ามีรูปภาพ ให้อัปโหลดรูปและเพิ่มคำสั่งพิเศษ
    if image_file:
        try:
            # แปลงไฟล์ที่อัปโหลดให้เป็น format ที่ PIL รู้จัก
            img = Image.open(image_file)
            contents.append(img) # เพิ่มรูปลงไปในแพ็คเกจที่จะส่ง
            
            # เพิ่มคำสั่งให้ AI ดูรูป
            contents[0] += """
            \n--- คำสั่งพิเศษ (Vision) ---
            **สำคัญมาก:** กรุณาวิเคราะห์ "รูปภาพ" ที่แนบมาด้วยอย่างละเอียด
            1. ดูว่าสินค้าในภาพคืออะไร สีอะไร วัสดุเป็นแบบไหน มีลักษณะเด่นอะไรที่ตาเห็น
            2. นำรายละเอียดที่เห็นในภาพจริง มาปรับแก้บทพูดและเขียน "บรีฟภาพ (Visual Prompt)" ให้ตรงกับของจริงที่สุด
            ---------------------------
            """
        except Exception as e:
            return f"เกิดข้อผิดพลาดกับการอ่านรูปภาพ: {e}"

    # คำสั่งปิดท้ายเรื่อง Format
    contents[0] += """
    \nขอ Output Format:
    ### ฉากที่ 1: [ชื่อฉาก]
    **🗣️ บทพูด:** [บทพูดสั้น กระชับ เข้าใจง่าย]
    **🎬 บรีฟภาพ:** [รายละเอียดภาพ มุมกล้อง การเคลื่อนไหว ที่อิงจากสินค้าจริงในรูป (ถ้ามี)]
    (ครบ 4 ฉาก: Hook, Problem, Solution, CTA)
    """

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    # ส่งแพ็คเกจ (ข้อความ + รูป) ไปให้ AI
    response = model.generate_content(contents)
    return response.text

# --- UI หน้าเว็บ ---
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    api_key = st.text_input("Gemini API Key", type="password")
    if st.button("เช็ก AI"):
        if get_valid_model(api_key): st.success("พร้อมใช้งาน!")
        else: st.error("API Key ผิด")

st.title("👁️ AI Script Gen (Vision Edition)")
st.caption("ระบบอัจฉริยะที่ 'มองเห็น' สินค้าของคุณ")

# ส่วนดึงข้อมูล (คงเดิม)
with st.expander("🔎 ดึงข้อมูลจากลิงก์ (ถ้ามี)"):
    col_url, col_btn = st.columns([3, 1])
    with col_url: url_input = st.text_input("วางลิงก์สินค้า (TikTok/Shopee/Lazada)")
    with col_btn:
        st.write("")
        st.write("")
        if st.button("ดึงข้อมูล", use_container_width=True) and url_input:
            with st.spinner("กำลังพยายามเจาะระบบ..."):
                title, desc = scrape_web(url_input)
                if title:
                    st.session_state.scraped_title = title
                    st.session_state.scraped_desc = desc
                    st.success("✅ เจอข้อมูล!")
                else:
                    st.warning("⚠️ เว็บป้องกัน กรุณากรอกเองและอัปโหลดรูปภาพช่วยครับ")

# ฟอร์มหลัก
with st.form("main_form"):
    st.subheader("📝 รายละเอียดสินค้า")
    
    # ช่องชื่อสินค้า
    product_name = st.text_input("ชื่อสินค้า (จำเป็น)", value=st.session_state.scraped_title)
    
    # === เพิ่มช่องอัปโหลดรูปภาพตรงนี้ ===
    st.write("---")
    st.markdown("**📸 อัปโหลดรูปสินค้า (แนะนำมาก!)**")
    st.caption("ช่วยให้ AI เห็นภาพจริง บรีฟภาพได้แม่นยำขึ้น โดยเฉพาะเวลาดึงข้อมูลจากลิงก์ไม่ได้")
    uploaded_image = st.file_uploader("เลือกไฟล์รูปภาพ (PNG, JPG, WEBP)", type=["png", "jpg", "jpeg", "webp"])
    
    if uploaded_image:
        st.image(uploaded_image, caption="รูปภาพที่จะส่งให้ AI", width=200)
    st.write("---")
    # =================================

    col1, col2 = st.columns(2)
    with col1: tone = st.selectbox("สไตล์", ["ตลก", "จริงจัง ผู้เชี่ยวชาญ", "เล่าเรื่อง", "ดราม่า"])
    with col2: features = st.text_area("จุดเด่น / ข้อมูลเพิ่มเติม", value=st.session_state.scraped_desc, height=100)
    
    submit_btn = st.form_submit_button("🚀 สร้างสคริปต์เดี๋ยวนี้", use_container_width=True)

if submit_btn:
    if not api_key: st.error("กรุณาใส่ API Key ก่อนครับ")
    elif not product_name and not uploaded_image: st.warning("กรุณาใส่ชื่อสินค้า หรืออัปโหลดรูปภาพอย่างใดอย่างหนึ่ง")
    else:
        with st.spinner("🤖 AI กำลังดูข้อมูลและรูปภาพ..."):
            model = get_valid_model(api_key)
            if model:
                # ส่งข้อมูลและรูปภาพไปให้ฟังก์ชันเจนสคริปต์
                res = generate_script(api_key, model, product_name, features, tone, url_input, uploaded_image)
                st.success(f"เรียบร้อย! (ใช้โมเดล: {model})")
                st.markdown("---")
                st.markdown(res)
            else: st.error("API Key มีปัญหา หรือหาโมเดลไม่เจอ")
