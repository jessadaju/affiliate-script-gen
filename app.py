import streamlit as st
import google.generativeai as genai
import cloudscraper
from bs4 import BeautifulSoup
import json
from PIL import Image

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script Gen (Viral Edition)", page_icon="🚀")

# --- Session State ---
if 'scraped_title' not in st.session_state: st.session_state.scraped_title = ""
if 'scraped_desc' not in st.session_state: st.session_state.scraped_desc = ""

# --- ฟังก์ชัน 1: ค้นหาโมเดลอัตโนมัติ ---
def get_valid_model(api_key):
    try:
        genai.configure(api_key=api_key)
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except: pass
        
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        for model_name in preferred_order:
            if model_name in available_models: return model_name
        return available_models[0] if available_models else 'models/gemini-1.5-flash'
    except: return None

# --- ฟังก์ชัน 2: ดึงข้อมูลเว็บ ---
def scrape_web(url):
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            final_title, final_desc = "", ""

            # JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if '@type' in data and data['@type'] == 'Product':
                        final_title = data.get('name', '')
                        final_desc = data.get('description', '')
                        break
                    if '@type' in data and data['@type'] == 'BreadcrumbList':
                        if 'itemListElement' in data: final_title = data['itemListElement'][-1]['item']['name']
                except: continue

            # Open Graph
            if not final_title:
                og_title = soup.find('meta', property='og:title')
                if og_title: final_title = og_title.get('content', '')
            if not final_desc:
                og_desc = soup.find('meta', property='og:description')
                if og_desc: final_desc = og_desc.get('content', '')

            if not final_title and soup.title: final_title = soup.title.string
            clean_title = final_title.split('|')[0].split(' - ')[0].strip()
            
            if clean_title: return clean_title, final_desc
            else: return None, "เว็บป้องกันหนาแน่น ไม่พบข้อมูล"
        else: return None, f"เข้าเว็บไม่ได้ (Status: {response.status_code})"
    except Exception as e: return None, f"Error: {str(e)}"

# --- ฟังก์ชัน 3: สร้างสคริปต์ (Viral & Short Prompt) ---
def generate_script(api_key, model_name, product, features, tone, url_info, image_file=None):
    
    # 🔥 PROMPT สูตรไวรัล: สั้น กระชับ เล่นกับความอยากรู้ 🔥
    prompt_text = f"""
    Role: Viral Content Creator (TikTok/Reels Expert).
    Task: Create content for product '{product}'.
    Language: Thai (Slang, Trendy, Super Short).
    
    Inputs:
    - Features: {features} {url_info}
    - Tone: {tone}
    
    Requirements:
    1. **Viral Caption:** - MAX 2 lines only! (Excluding hashtags).
       - Use "Curiosity Gap" or "Bold Statement" (e.g., "Don't buy if...", "Found it!").
       - Use 2-3 emojis.
    2. **SEO Hashtags:** - 5-8 Hashtags mixed of Trending & Niche.
    3. **Script (Fast-Paced):** - 4 Scenes. 
       - Scene 1 (Hook) must be < 3 seconds.
       - Use short sentences. No lecture style.
    4. **Visuals:** Match with the uploaded image (if any).

    Output Format:
    ## 🔥 Viral Caption
    [Short & Punchy Headline]
    [Call to Action in 1 sentence]
    
    [Hashtags]

    ## 🎬 Script (30s)
    ### Scene 1: Hook (Stop the scroll!)
    **🗣️ Speak:** ...
    **🖼️ Visual:** ...

    ### Scene 2: The Pain/Truth
    **🗣️ Speak:** ...
    **🖼️ Visual:** ...

    ### Scene 3: The Magic (Solution)
    **🗣️ Speak:** ...
    **🖼️ Visual:** ...

    ### Scene 4: Buy Now
    **🗣️ Speak:** ...
    **🖼️ Visual:** ...
    """
    
    contents = [prompt_text]

    if image_file:
        try:
            img = Image.open(image_file)
            contents.append(img)
            contents[0] += "\n\n**Note:** Look at the image. Describe the REAL product in 'Visual' sections."
        except Exception as e: return f"Image Error: {e}"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(contents)
    return response.text

# ================= UI หน้าเว็บ =================

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("Gemini API Key", type="password")
    if st.button("เช็ก AI"):
        if api_key and get_valid_model(api_key): st.success("พร้อมลุย!")
        else: st.error("Key ผิดจ้า")

st.title("🚀 Affiliate Script Gen (Viral Mode)")
st.caption("สูตรแคปชั่นสั้น เน้นไวรัล + สคริปต์เดินเรื่องไว")

# ส่วนดึงข้อมูล
with st.expander("🔎 ดึงข้อมูล (Optional)"):
    col_url, col_btn = st.columns([3, 1])
    with col_url: url_input = st.text_input("วางลิงก์สินค้า")
    with col_btn:
        st.write("")
        st.write("")
        if st.button("ดึงข้อมูล", use_container_width=True) and url_input:
            with st.spinner(".."):
                title, desc = scrape_web(url_input)
                if title:
                    st.session_state.scraped_title = title
                    st.session_state.scraped_desc = desc
                    st.success("✅")
                else: st.warning("⚠️")

# ฟอร์มหลัก
with st.form("main_form"):
    product_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
    st.markdown("**📸 รูปสินค้า (ช่วยให้ AI เห็นภาพจริง)**")
    uploaded_image = st.file_uploader("เลือกรูป", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_image: st.image(uploaded_image, width=150)
    
    col1, col2 = st.columns(2)
    with col1: tone = st.selectbox("สไตล์", ["ตลก/กวนๆ", "จริงจัง/รีวิวพลีชีพ", "ป้ายยาเพื่อนสาว", "ดราม่า/เล่าเรื่อง"])
    with col2: features = st.text_area("จุดเด่น", value=st.session_state.scraped_desc, height=100)
    
    submit = st.form_submit_button("⚡ สร้างสคริปต์ไวรัล", use_container_width=True)

if submit:
    if not api_key: st.error("ใส่ Key ก่อนนะ")
    elif not product_name and not uploaded_image: st.warning("ขอข้อมูลหน่อย")
    else:
        with st.spinner("🔥 กำลังปั้นความไวรัล..."):
            model = get_valid_model(api_key)
            if model:
                res = generate_script(api_key, model, product_name, features, tone, url_input, uploaded_image)
                st.success("เสร็จแล้ว! เอาไปโพสต์ได้เลย")
                st.markdown("---")
                st.markdown(res)
            else: st.error("Error AI")
