import streamlit as st
import google.generativeai as genai
import cloudscraper  # พระเอกคนใหม่
from bs4 import BeautifulSoup
import json

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Affiliate Script Gen (Pro)", page_icon="🎬")

# --- Session State ---
if 'scraped_title' not in st.session_state:
    st.session_state.scraped_title = ""
if 'scraped_desc' not in st.session_state:
    st.session_state.scraped_desc = ""

# --- ฟังก์ชันค้นหาโมเดล (คงเดิม) ---
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

# --- ฟังก์ชันดึงข้อมูล (อัปเกรดใหม่: Cloudscraper + JSON-LD) ---
def scrape_web(url):
    try:
        # ใช้ Cloudscraper แทน requests เพื่อทะลุ Cloudflare
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            final_title = ""
            final_desc = ""

            # เทคนิค 1: หาจาก JSON-LD (แม่นยำที่สุดสำหรับ Shopee/Lazada)
            # เว็บพวกนี้ชอบซ่อนข้อมูลไว้ใน script type="application/ld+json"
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    # ถ้าเจอว่าเป็น Product ให้ดึงชื่อเลย
                    if '@type' in data and data['@type'] == 'Product':
                        final_title = data.get('name', '')
                        final_desc = data.get('description', '')
                        break
                    # Shopee บางทีซ่อนอยู่ใน List
                    if '@type' in data and data['@type'] == 'BreadcrumbList':
                        # ดึงตัวสุดท้ายของ Breadcrumb มักเป็นชื่อสินค้า
                        if 'itemListElement' in data:
                            final_title = data['itemListElement'][-1]['item']['name']
                except:
                    continue

            # เทคนิค 2: ถ้า JSON-LD ไม่เจอ ให้หาจาก Open Graph
            if not final_title:
                og_title = soup.find('meta', property='og:title')
                if og_title and og_title.get('content'):
                    final_title = og_title['content']
            
            if not final_desc:
                og_desc = soup.find('meta', property='og:description')
                if og_desc and og_desc.get('content'):
                    final_desc = og_desc['content']

            # เทคนิค 3: ถ้ายังไม่เจออีก เอา Title หน้าเว็บ
            if not final_title:
                final_title = soup.title.string if soup.title else ""

            # คลีนข้อมูล
            clean_title = final_title.split('|')[0].strip()
            clean_title = clean_title.split(' - ')[0].strip()
            
            if clean_title:
                return clean_title, final_desc
            else:
                return None, "เว็บนี้ป้องกันหนาแน่นมาก หาข้อมูลไม่เจอครับ"
        else:
            return None, f"เข้าเว็บไม่ได้ (Status: {response.status_code})"
    except Exception as e:
        return None, f"Error: {str(e)}"

# --- ฟังก์ชันสร้างสคริปต์ (คงเดิม) ---
def generate_script(api_key, model_name, product, features, tone, url_info):
    prompt = f"""
    บทบาท: Creative Director มืออาชีพ
    งาน: เขียนสคริปต์ TikTok/Reels ขายของ ความยาว 30-45 วินาที
    ข้อมูลสินค้า: {product}
    ข้อมูลเพิ่มเติมจากลิงก์: {url_info}
    จุดเด่น: {features}
    โทน: {tone}
    
    ขอ Output Format:
    ### ฉากที่ 1: [ชื่อฉาก]
    **🗣️ บทพูด:** [บทพูด]
    **🎬 บรีฟภาพ:** [รายละเอียดภาพ]
    (ครบ 4 ฉาก: Hook, Problem, Solution, CTA)
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    return model.generate_content(prompt).text

# --- UI (คงเดิม) ---
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    api_key = st.text_input("Gemini API Key", type="password")
    if st.button("เช็ก AI"):
        if get_valid_model(api_key): st.success("พร้อมใช้งาน!")
        else: st.error("API Key ผิด")

st.title("🎬 AI Script Gen (Pro Scraper)")

# ส่วนดึงข้อมูล
with st.container(border=True):
    col_url, col_btn = st.columns([3, 1])
    with col_url:
        url_input = st.text_input("วางลิงก์สินค้า (TikTok/Shopee/Lazada)")
    with col_btn:
        st.write("")
        st.write("")
        if st.button("🔍 ดึงข้อมูล", use_container_width=True) and url_input:
            with st.spinner("กำลังเจาะระบบดึงข้อมูล..."):
                title, desc = scrape_web(url_input)
                if title:
                    st.session_state.scraped_title = title
                    st.session_state.scraped_desc = desc
                    st.success("✅ ดึงสำเร็จ!")
                else:
                    st.error("⚠️ ดึงไม่ได้ (เว็บป้องกัน) กรอกเองได้เลยครับ")

# ฟอร์มหลัก
with st.form("main_form"):
    product_name = st.text_input("ชื่อสินค้า", value=st.session_state.scraped_title)
    col1, col2 = st.columns(2)
    with col1: tone = st.selectbox("สไตล์", ["ตลก", "จริงจัง", "เล่าเรื่อง", "ดราม่า"])
    with col2: features = st.text_area("จุดเด่น", value=st.session_state.scraped_desc, height=100)
    
    if st.form_submit_button("🚀 สร้างสคริปต์") and api_key:
        with st.spinner("🤖 AI กำลังทำงาน..."):
            model = get_valid_model(api_key)
            if model:
                res = generate_script(api_key, model, product_name, features, tone, url_input)
                st.markdown("---")
                st.markdown(res)
            else: st.error("API Key มีปัญหา")
