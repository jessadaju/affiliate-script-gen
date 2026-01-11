import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script Gen (SEO+Vision)", page_icon="🔥")

# --- Session State (จำค่าข้อมูล) ---
if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

# --- ฟังก์ชัน 1: ค้นหาโมเดลอัตโนมัติ (แก้ปัญหา 404) ---
def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except: pass
        
        # ลำดับโมเดลที่อยากได้ (เน้น 1.5 เพราะฉลาดและดูรูปได้)
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        for model_name in preferred_order:
            if model_name in available_models: return model_name
        
        return available_models[0] if available_models else 'models/gemini-1.5-flash'
    except: return None

# --- ฟังก์ชัน 2: ดึงข้อมูลเว็บ (Cloudscraper + JSON-LD) ---
def scrape_web(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            final_title, final_desc = "", ""

            # สูตร 1: JSON-LD (แม่นสุด)
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

            # สูตร 2: Open Graph
            if not final_title:
                og_title = soup.find('meta', property='og:title')
                if og_title: final_title = og_title.get('content', '')
            if not final_desc:
                og_desc = soup.find('meta', property='og:description')
                if og_desc: final_desc = og_desc.get('content', '')

            # สูตร 3: Title ธรรมดา
            if not final_title and soup.title: final_title = soup.title.string

            # คลีนข้อมูล
            clean_title = final_title.split('|')[0].split(' - ')[0].strip()
            
            if clean_title: return clean_title, final_desc
            else: return None, "เว็บป้องกันหนาแน่น ไม่พบข้อมูล"
        else: return None, f"เข้าเว็บไม่ได้ (Status: {response.status_code})"
    except Exception as e: return None, f"Error: {str(e)}"

# --- ฟังก์ชัน 3: สร้างสคริปต์ (SEO & Vision Optimized) ---
def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    
    # Prompt ใหม่: เน้น SEO, Hashtag และความกระชับ
    prompt_text = f"""
    Role: Professional TikTok/Reels Content Strategist & SEO Expert.
    Task: Plan a viral video for product: '{product}'.
    Language: Thai (Natural, Engaging, Spoken style).
    
    Context Inputs:
    - Product Features: {features}
    - Info from Link: {url_info}
    - Mood/Tone: {tone}
    
    Requirements:
    1. **SEO Caption:** Write a compelling caption that includes 3-5 high-traffic keywords naturally.
    2. **Hashtags:** Provide 6-10 hashtags mixing broad (e.g., #TikTokพากิน) and niche tags.
    3. **Script Structure:** 4 Scenes (Hook -> Pain/Problem -> Solution/Benefit -> CTA). Keep it SHORT & PUNCHY.
    4. **Visual Prompts:** Describe exactly what to show. If an image is provided, MATCH the description to the real product (color, shape).

    Output Format:
    ## 📝 Caption & SEO
    **Caption:** [Caption with keywords]
    **Hashtags:** [List of hashtags]

    ## 🎬 Video Script (30-45s)
    ### Scene 1: Hook (3s)
    **🗣️ Speak:** [Stop-scrolling sentence]
    **🖼️ Visual:** [Specific visual detail]

    ### Scene 2: The Problem
    **🗣️ Speak:** [Relatable pain point]
    **🖼️ Visual:** [Visual showing the problem]

    ### Scene 3: The Solution
    **🗣️ Speak:** [Product benefit/How to use]
    **🖼️ Visual:** [Product showcase]

    ### Scene 4: Call to Action (CTA)
    **🗣️ Speak:** [Urgent command to buy]
    **🖼️ Visual:** [Pointing to basket/Flash sale overlay]
    """
    
    contents = [prompt_text]

    # จัดการรูปภาพ (ถ้ามี)
    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**IMPORTANT:** Analyze the attached image deeply. Ensure 'Visual' prompts match the REAL product details (Color, Material, Packaging) visible in the image."
        except Exception as e:
            return f"Image Error: {e}"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(contents)
    return response.text

# ================= UI หน้าเว็บ =================

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("Gemini API Key", type="password")
    st.info("ขอ Key ฟรีที่: aistudio.google.com")
    
    if st.button("เช็กสถานะ AI"):
        if not api_key: st.error("ใส่ Key ก่อนครับ")
        else:
            model = get_valid_model(api_key)
            if model: st.success(f"พร้อมใช้งาน! (Model: {model})")
            else: st.error("API Key ผิด หรือเชื่อมต่อไม่ได้")

st.title("🔥 Affiliate Script Gen (SEO Pro)")
st.caption("สร้างสคริปต์ + แคปชั่น SEO + บรีฟภาพจากสินค้าจริง")

# ส่วนดึงข้อมูล
with st.expander("🔎 ดึงข้อมูลจากลิงก์ (Optional)"):
    col_url, col_btn = st.columns([3, 1])
    with col_url: url_input = st.text_input("วางลิงก์สินค้า (TikTok/Shopee)")
    with col_btn:
        st.write("")
        st.write("")
        if st.button("ดึงข้อมูล", use_container_width=True) and url_input:
            with st.spinner("กำลังเจาะระบบ..."):
                title, desc = scrape_web(url_input)
                if title:
                    st.session_state.scraped_title = title
                    st.session_state.scraped_desc = desc
                    st.success("✅ ดึงสำเร็จ!")
                else: st.warning("⚠️ ดึงไม่ได้ กรอกเองด้านล่างครับ")

# ฟอร์มหลัก
with st.form("main_form"):
    st.subheader("1. ข้อมูลสินค้า")
    product_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
    
    st.markdown("**📸 รูปสินค้า (แนะนำมาก เพื่อความแม่นยำ)**")
    uploaded_image = st.file_uploader("เลือกรูปภาพ", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_image: st.image(uploaded_image, width=150)
    
    st.subheader("2. รายละเอียด")
    col1, col2 = st.columns(2)
    with col1: tone = st.selectbox("สไตล์คลิป", ["ตลก เฮฮา", "จริงจัง รีวิว", "เล่าเรื่อง Story", "ป้ายยาเพื่อนสาว"])
    with col2: features = st.text_area("จุดเด่น / โปรโมชั่น", value=st.session_state.scraped_desc, height=100)
    
    submit = st.form_submit_button("🚀 สร้างสคริปต์ SEO", use_container_width=True)

if submit:
    if not api_key: st.error("❌ ลืมใส่ API Key ครับ")
    elif not product_name and not uploaded_image: st.warning("⚠️ ขอชื่อสินค้า หรือรูปภาพหน่อยครับ")
    else:
        with st.spinner("🤖 AI กำลังวิเคราะห์รูปภาพและวางแผน SEO..."):
            model = get_valid_model(api_key)
            if model:
                res = generate_script(api_key, model, product_name, features, tone, url_input, uploaded_image)
                st.success("เรียบร้อย! คัดลอกไปใช้ได้เลย")
                st.markdown("---")
                st.markdown(res)
            else: st.error("เชื่อมต่อ AI ไม่ได้ (เช็ก Key/Model)")
