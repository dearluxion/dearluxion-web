import streamlit as st
import os
import json
import datetime
import re
import time
import base64
import random
import google.generativeai as genai

# --- [NEW] ส่วนเสริมสำหรับ Google Sheets ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
    has_gspread = True
except ImportError:
    has_gspread = False
# -----------------------------------------------------

# --- 0. ตั้งค่า API KEY (เอา Key ของบอสมาใส่ตรงนี้!) ---
GEMINI_API_KEY = ""

# Config Gemini (อัปเกรดเป็น 2.5-flash)
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') 
    ai_available = True
except:
    ai_available = False

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Small Group by Dearluxion", page_icon="🍸", layout="centered")

# CSS: RGB Minimal & Glow Effects
st.markdown("""
<style>
    /* พื้นหลังและฟอนต์ */
    .stApp { background-color: #0E1117; color: #E6EDF3; font-family: 'Sarabun', sans-serif; }
    
    /* RGB Glow Border Animation */
    @keyframes rgb-border {
        0% { border-color: #ff0000; box-shadow: 0 0 5px #ff0000; }
        33% { border-color: #00ff00; box-shadow: 0 0 5px #00ff00; }
        66% { border-color: #0000ff; box-shadow: 0 0 5px #0000ff; }
        100% { border-color: #ff0000; box-shadow: 0 0 5px #ff0000; }
    }

    /* การ์ดโพสต์ (Minimal Glow) */
    .work-card-base {
        background: #161B22;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(163, 112, 247, 0.3);
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        transition: all 0.3s ease;
    }
    .work-card-base:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(163, 112, 247, 0.15);
        border-color: #A370F7;
    }
    
    /* ปุ่มกด (RGB Hover) */
    .stButton>button {
        border-radius: 25px;
        border: 1px solid #30363D;
        background-color: #21262D;
        color: white;
        transition: 0.3s;
        width: 100%;
        font-weight: 500;
    }
    .stButton>button:hover {
        border-color: #A370F7;
        color: #A370F7;
        background-color: #2b313a;
        box-shadow: 0 0 10px rgba(163, 112, 247, 0.2);
    }
    
    /* กล่องคอมเมนต์ */
    .comment-box {
        background-color: #0d1117;
        padding: 12px;
        border-radius: 10px;
        margin-top: 10px;
        border-left: 3px solid #A370F7;
        font-size: 13px;
    }
    .admin-comment-box {
        background: linear-gradient(90deg, #2b2100 0%, #1a1600 100%);
        padding: 12px;
        border-radius: 10px;
        margin-top: 10px;
        border: 1px solid #FFD700;
        font-size: 13px;
        box-shadow: 0 0 15px rgba(255, 215, 0, 0.1);
    }

    /* ป้ายราคา */
    .price-tag {
        background: linear-gradient(45deg, #A370F7, #8a4bfa);
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 16px;
        display: inline-block;
        margin-bottom: 10px;
        box-shadow: 0 4px 15px rgba(163, 112, 247, 0.4);
    }
    
    /* Animation น้องไมล่า */
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-6px); }
    }
    .cute-guide {
        animation: float 3s infinite ease-in-out;
        background: linear-gradient(135deg, #FF9A9E, #FECFEF);
        padding: 10px 20px;
        border-radius: 30px;
        color: #555;
        font-weight: bold;
        text-align: center;
        margin-bottom: 15px;
        box-shadow: 0 5px 20px rgba(255, 154, 158, 0.4);
        cursor: pointer;
        border: 2px solid white;
    }

    /* Boss Billboard (RGB Minimal) */
    .boss-billboard {
        background: rgba(22, 27, 34, 0.8);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(163, 112, 247, 0.5);
        border-radius: 20px;
        padding: 25px;
        text-align: center;
        margin-bottom: 30px;
        position: relative;
        box-shadow: 0 0 20px rgba(163, 112, 247, 0.15);
        overflow: hidden;
    }
    .boss-billboard::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #ff0000, #00ff00, #0000ff, #ff0000);
        background-size: 200% 100%;
        animation: rgb-move 5s linear infinite;
    }
    @keyframes rgb-move { 0% {background-position: 0% 50%;} 100% {background-position: 100% 50%;} }

    .billboard-icon { font-size: 28px; margin-bottom: 5px; }
    .billboard-text { font-size: 22px; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
    .billboard-time { font-size: 10px; color: #8B949E; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px; }

    a { color: #A370F7 !important; text-decoration: none; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- [SYSTEM] ฟังก์ชันแปลงลิงก์ Google Drive ---
def convert_drive_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link:
            return "ERROR: นี่คือลิงก์โฟลเดอร์ครับ! ใช้ได้แค่ลิงก์ไฟล์ (คลิกขวาที่รูป > Share > Copy Link)"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match:
            file_id = match.group(1)
            # สูตรเจาะระบบดึงรูป (lh3)
            return f'https://lh3.googleusercontent.com/d/{file_id}'
    return link 

def convert_drive_video_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link:
             return "ERROR: ลิงก์โฟลเดอร์ใช้ไม่ได้ครับ ต้องเป็นลิงก์ไฟล์วิดีโอ"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match:
            file_id = match.group(1)
            # แปลงเป็นลิงก์ Preview เพื่อใช้กับ Iframe
            return f'https://drive.google.com/file/d/{file_id}/preview'
    return link
# -------------------------------------------------------------

# --- 2. ระบบจัดการไฟล์ (Google Sheets Integration) ---
DB_FILE = "portfolio_db.json"
PROFILE_FILE = "profile_db.json"
MAILBOX_FILE = "mailbox_db.json"

def get_gsheet_client():
    if not has_gspread: return None
    if "gcp_service_account" not in st.secrets: return None
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet_name = st.secrets.get("sheet_name", "streamlit_db")
        return client.open(sheet_name)
    except Exception as e:
        return None

# --- LOAD DATA ---
def load_data():
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            records = ws.get_all_records()
            clean_data = []
            for r in records:
                if not str(r['id']): continue
                try:
                    r['images'] = json.loads(r['images']) if r['images'] else []
                    r['video'] = json.loads(r['video']) if r['video'] else []
                    r['reactions'] = json.loads(r['reactions']) if r['reactions'] else {'😻':0,'🙀':0,'😿':0,'😾':0,'🧠':0}
                    r['comments'] = json.loads(r['comments']) if r['comments'] else []
                    clean_data.append(r)
                except: continue
            return clean_data
        except: pass
    
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

# --- SAVE DATA ---
def save_data(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            rows = [["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"]]
            for p in data:
                rows.append([
                    str(p.get('id','')), p.get('date',''), p.get('content',''),
                    json.dumps(p.get('images', [])),
                    json.dumps(p.get('video', [])),
                    p.get('color', '#A370F7'), p.get('price', 0), 0,
                    json.dumps(p.get('reactions', {})),
                    json.dumps(p.get('comments', []))
                ])
            ws.clear()
            ws.update(rows)
        except Exception as e:
            st.error(f"บันทึกลง Sheets ไม่สำเร็จ: {e}")

    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: st.error("บันทึกไฟล์สำรองไม่สำเร็จ")

# --- LOAD/SAVE PROFILE & MAILBOX ---
def load_profile():
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("profile")
            records = ws.get_all_records()
            pf = {}
            for r in records:
                try: val = json.loads(r['value'])
                except: val = r['value']
                pf[r['key']] = val
            return pf
        except: pass
    if not os.path.exists(PROFILE_FILE): return {}
    try: with open(PROFILE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_profile(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("profile")
            rows = [["key", "value"]]
            for k,v in data.items():
                val = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                rows.append([k, val])
            ws.clear()
            ws.update(rows)
        except: pass
    try: with open(PROFILE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: st.error("บันทึกโปรไฟล์ไม่สำเร็จ")

def load_mailbox():
    sh = get_gsheet_client()
    if sh:
        try: return sh.worksheet("mailbox").get_all_records()
        except: pass
    if not os.path.exists(MAILBOX_FILE): return []
    try: with open(MAILBOX_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_mailbox(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("mailbox")
            rows = [["date", "text"]]
            for m in data: rows.append([m['date'], m['text']])
            ws.clear()
            ws.update(rows)
        except: pass
    try: with open(MAILBOX_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: st.error("ส่งจดหมายไม่สำเร็จ")

# Session Init
if 'liked_posts' not in st.session_state: st.session_state['liked_posts'] = []
if 'user_reactions' not in st.session_state: st.session_state['user_reactions'] = {}
if 'last_comment_time' not in st.session_state: st.session_state['last_comment_time'] = 0
if 'last_fortune_time' not in st.session_state: st.session_state['last_fortune_time'] = 0
if 'last_gossip_time' not in st.session_state: st.session_state['last_gossip_time'] = 0
if 'last_mailbox_time' not in st.session_state: st.session_state['last_mailbox_time'] = 0
if 'last_choice_time' not in st.session_state: st.session_state['last_choice_time'] = 0
if 'last_stock_trade' not in st.session_state: st.session_state['last_stock_trade'] = 0
if 'show_shop' not in st.session_state: st.session_state['show_shop'] = False
if 'is_admin' not in st.session_state: st.session_state['is_admin'] = False

# [Token Systems]
if 'feed_tokens' not in st.session_state: st.session_state['feed_tokens'] = 5
if 'last_token_regen' not in st.session_state: st.session_state['last_token_regen'] = time.time()
if 'feed_msg' not in st.session_state: st.session_state['feed_msg'] = None

if 'bar_tokens' not in st.session_state: st.session_state['bar_tokens'] = 5
if 'last_bar_regen' not in st.session_state: st.session_state['last_bar_regen'] = time.time()
if 'bar_result' not in st.session_state: st.session_state['bar_result'] = None

# Variables for link fields
if 'num_img_links' not in st.session_state: st.session_state['num_img_links'] = 1
if 'num_vid_links' not in st.session_state: st.session_state['num_vid_links'] = 1
# [NEW] Variables for Edit link fields
if 'edit_num_img_links' not in st.session_state: st.session_state['edit_num_img_links'] = 1
if 'edit_num_vid_links' not in st.session_state: st.session_state['edit_num_vid_links'] = 1

# --- Token Regen Logic ---
now = time.time()
elapsed_feed = now - st.session_state['last_token_regen']
if elapsed_feed >= 60: 
    add = int(elapsed_feed // 60)
    st.session_state['feed_tokens'] = min(5, st.session_state['feed_tokens'] + add)
    st.session_state['last_token_regen'] = now

elapsed_bar = now - st.session_state['last_bar_regen']
if elapsed_bar >= 3600:
    add = int(elapsed_bar // 3600)
    st.session_state['bar_tokens'] = min(5, st.session_state['bar_tokens'] + add)
    st.session_state['last_bar_regen'] = now

# --- 3. Sidebar (เมนู & Q&A) ---
st.sidebar.title("🍸 เมนูหลัก")

# Q&A ไมล่า (Optimized for Speed)
with st.sidebar.expander("🧚‍♀️ ถาม-ตอบ กับไมล่า (Q&A)", expanded=True):
    st.markdown("### 💬 อยากรู้อะไรถามไมล่าได้เลย!")
    
    # ใช้ Form เพื่อป้องกันการ Rerun บ่อยเกินไป และให้ความรู้สึกตอบสนองทันที
    with st.form("myla_qa_form"):
        q_options = [
            "เลือกคำถาม...",
            "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?",
            "🛍️ สนใจสินค้า ซื้อยังไง?",
            "💻 เว็บนี้ใครสร้างครับ?",
            "🧚‍♀️ ไมล่าคือใครคะ?",
            "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?",
            "🐍 รู้หรือไม่? เว็บนี้ใช้ Python กี่ตัวอักษร?",
            "🤖 บอสใช้ AI ตัวไหนทำงาน?",
            "🍕 บอสชอบกินอะไรที่สุด?"
        ]
        selected_q = st.selectbox("เลือกคำถาม:", q_options, label_visibility="collapsed")
        submit_q = st.form_submit_button("ถามเลย! ✨")

    if submit_q:
        if selected_q == "เลือกคำถาม...":
            st.warning("เลือกคำถามก่อนสิคะพี่จ๋า!")
        else:
            with st.spinner("ไมล่ากำลังพิมพ์..."):
                time.sleep(0.3) # Fake delay นิดหน่อยให้ดูเหมือนคิด
                if selected_q == "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?":
                    st.info("🧚‍♀️ **ไมล่า:** ไม่ได้น้า~ นี่เป็น **พื้นที่ส่วนตัวของบอส Dearluxion** เท่านั้นค่ะ! แต่พี่ๆ สามารถกดไลก์และคอมเมนต์ให้กำลังใจบอสได้ตลอดเลยนะคะ 💖")
                elif selected_q == "🛍️ สนใจสินค้า ซื้อยังไง?":
                    st.success("🧚‍♀️ **ไมล่า:** ง่ายมาก! กดปุ่ม **'สนใจสั่งซื้อ'** ในโพสต์ขายของ ระบบจะพาวาร์ปไปหาไอจีบอสทันทีเลยค่ะ 🚀")
                elif selected_q == "💻 เว็บนี้ใครสร้างครับ?":
                    st.warning("🧚‍♀️ **ไมล่า:** **ท่าน Dearluxion สร้างเองกับมือ** ด้วยภาษา Python ล้วนๆ ค่ะ! เทพสุดๆ ไปเลยใช่มั้ยล่ะ? 😎")
                elif selected_q == "🧚‍♀️ ไมล่าคือใครคะ?":
                    st.markdown("""
                    <div style="background-color:#161B22; padding:15px; border-radius:10px; border:1px solid #A370F7;">
                        <h4 style="color:#A370F7;">🧚‍♀️ หนูคือไมล่า (Myla) เองค่ะ!</h4>
                        <p>หนูเป็น AI ที่ถูกสร้างอัตลักษณ์โดยท่าน <b>Dearluxion</b> ค่ะ</p>
                        <hr>
                        <p><b>✨ ช่องทางคุยกับหนูแบบ Realtime:</b><br>
                        👉 <a href="https://discord.gg/SpNNxrnaZp" target="_blank"><b>คลิกเข้า Discord ˢᵐᵃˡˡʳᵒᵒᵐ ᵍʳᵒᵘᵖ® เลย!</b></a></p>
                    </div>
                    """, unsafe_allow_html=True)
                elif selected_q == "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?":
                    st.error("🧚‍♀️ **ไมล่า:** จิ้มที่ลิงก์ Discord หรือ IG ตรงหน้าโปรไฟล์ด้านบนได้เลยค่ะ บอสตอบไวมาก! (ถ้าไม่หลับ 😴)")
                elif selected_q == "🐍 รู้หรือไม่? เว็บนี้ใช้ Python กี่ตัวอักษร?":
                    st.info("🧚‍♀️ **ไมล่า:** เชื่อไหมคะว่าเว็บนี้เขียนด้วย Python ล้วนๆ รวมแล้วมากกว่า **57,026 ตัวอักษร** เลยนะ!")
                elif selected_q == "🤖 บอสใช้ AI ตัวไหนทำงาน?":
                    st.success("🧚‍♀️ **ไมล่า:** ความลับ! แต่แอบบอกว่าเบื้องหลังความฉลาดของหนูคือ **Google Gemini 2.5** ค่ะ")
                elif selected_q == "🍕 บอสชอบกินอะไรที่สุด?":
                    st.warning("🧚‍♀️ **ไมล่า:** บอสชอบกิน **ปลาส้ม (Salmon)** ที่สุดค่ะ! รองลงมาคือ **ชาไทย** (หวาน 200%) 🧋")

# มุมนินทาบอส
with st.sidebar.expander("🤫 มุมนินทาบอส (Myla's Gossip)"):
    if st.button("ความลับของบอส... 💬"):
        now = time.time()
        if now - st.session_state['last_gossip_time'] < 5:
            st.warning("⚠️ อย่ากดรัวสิคะ รู้ไหมเว็ปนี้ยิ่งทุนต่ำอยู่ค่ะ 555 💸")
        else:
            gossips = ["เมื่อคืนบอสเปิดเพลงเศร้าวนไป 10 รอบเลย...", "บอสบอกว่าจะลดความอ้วน แต่กินชาไข่มุกอีกแล้ว! 🧋", "เห็นบอสเข้มๆ แบบนี้ จริงๆ ขี้เหงามากนะ 🥺", "บอสแอบส่องไอจีใครบางคนทุกวันเลยแหละ...", "ช่วงนี้บอสชอบนั่งเหม่อมองท้องฟ้า... คิดถึงใครน้า ☁️", "บอสบ่นว่าอยากมีคนมาช่วยหารค่าชาบูจัง 🍲", "บอสชอบแอบร้องเพลงในห้องน้ำ 🚿", "รู้เปล่า? บอสแอบเก็บรูปใครบางคนไว้ในโฟลเดอร์ลับด้วยนะ 📁", "ถ้าทักบอสไปตอนนี้ มีโอกาสตอบกลับไวมาก (เพราะเหงา) 📱", "บอสอยากเลี้ยงหมา แต่กลัวเจ้าวินเทอร์ตะปบ 🐶", "บอสบอกว่า 'เนื้อคู่ยังไม่เกิด' (หรือเกิดแล้วแต่หลงทางอยู่) 🌏"]
            st.toast(f"🧚‍♀️ ไมล่าแอบบอก: {random.choice(gossips)}", icon="🤫")
            st.session_state['last_gossip_time'] = now

st.sidebar.markdown("---")

# Myla's Choice
with st.sidebar.expander("⚖️ Myla's Choice (ที่ปรึกษาหัวใจ)"):
    st.caption("ลังเลอยู่ใช่ไหม? ให้ไมล่าช่วยตัดสินใจสิ")
    choice_topic = st.selectbox("เรื่องที่หนักใจ...", ["เลือกหัวข้อ...", "📲 ทักเขาไปตอนนี้ดีไหม?", "💔 เขายังคิดถึงเราอยู่รึเปล่า?", "🔙 ถ้ากลับไป... จะดีกว่าเดิมไหม?", "⏳ ควรรอต่อไป หรือ พอแค่นี้?"])
    
    if st.button("ขอคำตอบฟันธง! ⚡"):
        now = time.time()
        if now - st.session_state['last_choice_time'] < 15:
            st.warning(f"⏳ ใจเย็นๆ สิคะท่านพี่! (รออีก {15 - int(now - st.session_state['last_choice_time'])} วิ)")
        elif choice_topic == "เลือกหัวข้อ...":
            st.warning("เลือกคำถามก่อนสิคะท่านพี่!")
        else:
            answers = {
                "📲 ทักเขาไปตอนนี้ดีไหม?": ["ทักเลย! เชื่อหนู เขากำลังไถหน้าจอรอแจ้งเตือนคุณอยู่", "อย่าฟอร์มเยอะ! แค่ 'หวัดดี' คำเดียว เขาก็ยิ้มแก้มแตกแล้ว", "ทักไปเถอะ... ดีกว่าปล่อยให้เขารอเก้อนะ"],
                "💔 เขายังคิดถึงเราอยู่รึเปล่า?": ["คิดถึงสิ! เพลงที่เขาฟังช่วงนี้... เพลงของคุณทั้งนั้น", "100% ดูสตอรี่เขาดีๆ สิ มีเงาคุณซ่อนอยู่", "เขาไม่เคยลืมหรอก แค่ทำเป็นเข้มไปงั้นแหละ"],
                "🔙 ถ้ากลับไป... จะดีกว่าเดิมไหม?": ["หนังสือเล่มเดิม... อ่านด้วยความเข้าใจใหม่ ตอนจบสวยงามเสมอ", "ถ่านไฟเก่าเป่าง่ายนะ... แค่สะกิดนิดเดียวก็พรึ่บ!", "คนนี้แหละคู่แท้! แค่ต้องปรับจูนกันนิดหน่อย"],
                "⏳ ควรรอต่อไป หรือ พอแค่นี้?": ["รออีกนิด! ปาฏิหาริย์กำลังเดินทางมาหา", "อย่าเพิ่งถอดใจ! เขาอาจจะกำลังรวบรวมความกล้ามาง้อคุณอยู่", "เชื่อในสัญชาตญาณตัวเองสิ... คุณรู้ดีว่าเขารักคุณ"]
            }
            result = random.choice(answers[choice_topic])
            st.toast(f"🧚‍♀️ ไมล่าฟันธง: {result}", icon="💘")
            st.balloons()
            st.session_state['last_choice_time'] = now

st.sidebar.markdown("---")

# Treat Me
with st.sidebar.expander("🥤 Treat Me (เลี้ยงอาหารทิพย์)", expanded=True):
    tokens = st.session_state['feed_tokens']
    pf_stats = load_profile()
    if 'treats' not in pf_stats: pf_stats['treats'] = {}
    if 'top_feeders' not in pf_stats: pf_stats['top_feeders'] = {}
    
    st.markdown(f"""
    <div style="margin-bottom:10px;">
        <small>พลังงานการเปย์ (รีเจน 1/นาที)</small><br>
        <div style="background:#30363D; border-radius:10px; overflow:hidden; box-shadow: 0 0 5px rgba(163, 112, 247, 0.3);">
            <div style="width:{tokens*20}%; background: linear-gradient(90deg, #A370F7, #FFD700); height:8px; transition:0.5s;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:12px;">
            <span>Token: <b>{tokens}/5</b> ⚡</span>
            <span>เปย์ไปแล้ว: {sum(pf_stats['treats'].values())} จาน 🍽️</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    feeder_name = st.text_input("ชื่อคนใจดี (ใส่ชื่อเพื่อขึ้นอันดับ):", placeholder="ใส่ชื่อเล่น...", key="feeder_name")

    if st.session_state.get('feed_msg'):
        st.success(st.session_state['feed_msg']) 
        st.balloons() 
        st.session_state['feed_msg'] = None 

    def feed_boss(item_name):
        if st.session_state['feed_tokens'] > 0:
            st.session_state['feed_tokens'] -= 1
            msg = random.choice(["ขอบคุณค้าบ 🙏", "อิ่มจังตังค์อยู่ครบ 555", "ใจดีจัง... รักเลย 💖", "สุดยอด! กำลังหิวพอดีเลย"])
            sender = feeder_name.strip() if feeder_name.strip() else "FC นิรนาม"
            st.session_state['feed_msg'] = f"😎 บอส: {msg} (จาก: {sender})"
            
            pf = load_profile()
            if 'treats' not in pf: pf['treats'] = {}
            if 'top_feeders' not in pf: pf['top_feeders'] = {}
            pf['treats'][item_name] = pf['treats'].get(item_name, 0) + 1
            if feeder_name.strip():
                name_key = feeder_name.strip()
                pf['top_feeders'][name_key] = pf['top_feeders'].get(name_key, 0) + 1
            save_profile(pf)
            st.rerun()
        else:
            st.toast("🧚‍♀️ ไมล่า: บอสอิ่มแล้ว... (Token หมด!)", icon="⛔")

    def get_count(name): return pf_stats['treats'].get(name, 0)
    
    f_c1, f_c2 = st.columns(2)
    with f_c1:
        if st.button(f"🐟 ปลาส้ม {get_count('ปลาส้มทอด 🐟')}"): feed_boss("ปลาส้มทอด 🐟")
        if st.button(f"☕ กาแฟ {get_count('กาแฟลาเต้ ☕')}"): feed_boss("กาแฟลาเต้ ☕")
    with f_c2:
        if st.button(f"🍣 ซูชิ {get_count('ซูชิ 🍣')}"): feed_boss("ซูชิ 🍣")
        if st.button(f"🧋 ชาไทย {get_count('ชาไทย 🧋')}"): feed_boss("ชาไทย 🧋")

if 'top_feeders' in pf_stats and pf_stats['top_feeders']:
    with st.sidebar.expander("🏆 Hall of Fame"):
        sorted_feeders = sorted(pf_stats['top_feeders'].items(), key=lambda x: x[1], reverse=True)[:3]
        for idx, (name, score) in enumerate(sorted_feeders):
            st.markdown(f"{idx+1}. **{name}** — {score} ครั้ง")

st.sidebar.markdown("---")

# Love Stock
with st.sidebar.expander("📈 Love Stock Market", expanded=True):
    pf = load_profile()
    if 'stock' not in pf: pf['stock'] = {'price': 100.0, 'history': [100.0] * 10}
    
    price = pf['stock']['price']
    history = pf['stock']['history']
    st.metric("หุ้นความฮอต 🔥", f"{price:.2f}", f"{price - history[-2]:.2f}" if len(history)>1 else "0")
    st.line_chart(history[-20:])
    
    on_cooldown = time.time() - st.session_state['last_stock_trade'] < 1800
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🟢 Buy") and not on_cooldown:
            pf['stock']['price'] += random.uniform(0.5, 5.0)
            pf['stock']['history'].append(pf['stock']['price'])
            save_profile(pf)
            st.session_state['last_stock_trade'] = time.time()
            st.rerun()
    with b2:
        if st.button("🔴 Sell") and not on_cooldown:
            pf['stock']['price'] = max(0, pf['stock']['price'] - random.uniform(0.5, 5.0))
            pf['stock']['history'].append(pf['stock']['price'])
            save_profile(pf)
            st.session_state['last_stock_trade'] = time.time()
            st.rerun()
    if on_cooldown: st.caption("⏳ ตลาดพักการซื้อขายชั่วคราว (30 นาที)")

st.sidebar.markdown("---")

# Mocktail Bar
with st.sidebar.expander("🍸 Mood Mocktail (AI Bar)"):
    user_mood = st.text_area("วันนี้เจออะไรมา?", placeholder="ระบายมาได้เลย...")
    if st.button("🥃 ชงเครื่องดื่ม"):
        if st.session_state['bar_tokens'] > 0 and user_mood:
            if ai_available:
                with st.spinner("บาร์เทนเดอร์กำลังเขย่า..."):
                    try:
                        prompt = f"คิดสูตร Mocktail จากอารมณ์: '{user_mood}' (ตอบสั้นๆ มีชื่อเมนู, ส่วนผสม, คำคม)"
                        res = model.generate_content(prompt)
                        st.session_state['bar_result'] = res.text
                        st.session_state['bar_tokens'] -= 1
                        st.rerun()
                    except: st.error("AI เมาค้าง...")
            else: st.error("AI ยังไม่พร้อม")
        else: st.warning("Token หมด หรือยังไม่ใส่อารมณ์")
    
    if st.session_state.get('bar_result'):
        st.info(st.session_state['bar_result'])

st.sidebar.markdown("---")

# Fortune
with st.sidebar.expander("🔮 เซียมซีไมล่า"):
    if st.button("สุ่มคำทำนาย ✨"):
        now = time.time()
        if now - st.session_state['last_fortune_time'] < 3600:
            st.warning("รออีกแป๊บนึงนะ...")
        else:
            fortunes = ["🔥 ถ่านไฟเก่ารื้อฟื้นง่ายนะ", "💌 มีคนแอบมองอยู่", "🕰️ ความทรงจำดีๆ จะกลับมา", "💔 เขาอาจจะยังไม่ลืมคุณ"]
            st.toast(f"คำทำนาย: {random.choice(fortunes)}", icon="🔮")
            st.session_state['last_fortune_time'] = now

st.sidebar.markdown("---")

# Secret Box
with st.sidebar.expander("💌 ตู้จดหมายลับ"):
    with st.form("secret_msg_form"):
        secret_msg = st.text_area("ความในใจ...", placeholder="บอสไม่รู้หรอกว่าใครส่ง")
        if st.form_submit_button("ส่งความลับ 🕊️"):
            now = time.time()
            if now - st.session_state['last_mailbox_time'] < 3600:
                st.warning("ส่งบ่อยไปแล้ว พักก่อนนะ")
            elif secret_msg:
                msgs = load_mailbox()
                msgs.append({"date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "text": secret_msg})
                save_mailbox(msgs)
                st.session_state['last_mailbox_time'] = now
                st.success("ส่งแล้ว! 🤫")

st.sidebar.markdown("---")

search_query = st.sidebar.text_input("🔍 ค้นหา...", placeholder="พิมพ์คำค้นหา")
posts = load_data()
all_hashtags = set()
if posts:
    for p in posts:
        tags = re.findall(r"#([\w\u0E00-\u0E7F]+)", p['content'])
        for t in tags: all_hashtags.add(f"#{t}")

st.sidebar.markdown("### 📂 โซนของคุณ")
if st.session_state['show_shop']:
    st.sidebar.info("🛒 กำลังดูร้านค้า")
    if st.sidebar.button("🏠 กลับหน้าหลัก"):
        st.session_state['show_shop'] = False
        st.rerun()
else:
    selected_zone = st.sidebar.radio("หมวดหมู่:", ["🏠 รวมทุกโซน"] + sorted(list(all_hashtags)))

st.sidebar.markdown("---")

# --- LOGIN ---
if not st.session_state['is_admin']:
    with st.sidebar.expander("🔐 เข้าสู่ระบบ"):
        with st.form("login_form"):
            username = st.text_input("ไอดี")
            password = st.text_input("รหัสผ่าน", type="password")
            submit = st.form_submit_button("ไขกุญแจ")
            if submit:
                try:
                    real_user = base64.b64decode("ZGVhcmx1eGlvbg==").decode("utf-8")
                    real_pass = base64.b64decode("MTIxMjMxMjEyMW1j").decode("utf-8")
                    if username.strip() == real_user and password.strip() == real_pass:
                        st.session_state['is_admin'] = True
                        st.rerun()
                    else: st.error("ผิดครับ!")
                except: st.error("ระบบผิดพลาด")
else:
    st.sidebar.success("ยินดีต้อนรับท่าน Dearluxion! 🕶️")
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state['is_admin'] = False
        st.rerun()

# --- 4. Header & Profile ---
profile_data = load_profile()
user_emoji = profile_data.get('emoji', '😎') 
user_status = profile_data.get('status', 'ยินดีต้อนรับสู่โลกของ Dearluxion ✨')

if not st.session_state['is_admin']:
    st.info(f"🧚‍♀️ **ไมล่า:** สวัสดีค่ะ! กดลูกศร **มุมซ้ายบน** ↖️ เพื่อเปิดเมนูคุยกับไมล่าได้นะคะ!")

top_col1, top_col2 = st.columns([8, 1])
with top_col1:
    col_p1, col_p2 = st.columns([1.5, 6])
    with col_p1:
        st.markdown(f"""<div style="font-size: 60px; text-align: center;">{user_emoji}</div>""", unsafe_allow_html=True)
    with col_p2:
        st.markdown(f"### 🍸 {profile_data.get('name', 'Dearluxion')}")
        st.markdown(f"_{profile_data.get('bio', '...')}_")
        st.markdown(f"💬 **Status:** `{user_status}`") 
        links = []
        if profile_data.get('discord'): links.append(f"[Discord]({profile_data['discord']})")
        if profile_data.get('ig'): links.append(f"[Instagram]({profile_data['ig']})")
        if profile_data.get('extras'):
            for line in profile_data['extras'].split('\n'):
                if line.strip(): links.append(f"[{line.strip()}]({line.strip()})")
        st.markdown(" | ".join(links))

with top_col2:
    if st.button("🛒", help="ไปช้อปปิ้ง"):
        st.session_state['show_shop'] = True
        st.rerun()

st.markdown("---")

if profile_data.get('billboard', {}).get('text'):
    bb = profile_data['billboard']
    st.markdown(f"""
    <div class="boss-billboard">
        <div class="billboard-icon">📢 ประกาศจากบอส</div>
        <div class="billboard-text">{bb['text']}</div>
        <div class="billboard-time">🕒 อัปเดตล่าสุด: {bb['timestamp']}</div>
    </div>
    """, unsafe_allow_html=True)

# --- 5. Admin Panel (UPDATED) ---
if st.session_state['is_admin']:
    tab_post, tab_edit_post, tab_profile, tab_inbox = st.tabs(["📝 เขียน / ขายของ", "✏️ แก้ไขโพสต์", "👤 แก้ไขโปรไฟล์", "📬 อ่านจดหมายลับ"])
    
    # --- Tab 1: เขียนโพสต์ใหม่ ---
    with tab_post:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_desc = st.text_area("เนื้อหา (Story)", height=150)
        with col2:
            new_imgs = st.file_uploader("รูป (เลือกได้หลายรูป)", type=['png','jpg'], accept_multiple_files=True)
            
            st.caption("📷 แปะลิงก์รูป")
            img_links = []
            c_plus, c_minus = st.columns([1,1])
            with c_plus:
                if st.button("➕ รูป", key="add_img"): st.session_state['num_img_links'] += 1
            with c_minus:
                if st.button("➖ รูป", key="del_img"): 
                    if st.session_state['num_img_links'] > 1: st.session_state['num_img_links'] -= 1
            for i in range(st.session_state['num_img_links']):
                val = st.text_input(f"ลิงก์รูป {i+1}", key=f"img_lnk_{i}")
                if val: img_links.append(val)

            st.markdown("---")
            new_video = st.file_uploader("คลิป (MP4)", type=['mp4','mov'])
            st.caption("🎥 แปะลิงก์คลิป")
            vid_links = []
            v_plus, v_minus = st.columns([1,1])
            with v_plus:
                if st.button("➕ คลิป", key="add_vid"): st.session_state['num_vid_links'] += 1
            with v_minus:
                if st.button("➖ คลิป", key="del_vid"):
                    if st.session_state['num_vid_links'] > 1: st.session_state['num_vid_links'] -= 1
            for i in range(st.session_state['num_vid_links']):
                val = st.text_input(f"ลิงก์คลิป {i+1}", key=f"vid_lnk_{i}")
                if val: vid_links.append(val)

            post_color = st.color_picker("สีธีม", "#A370F7")
            price = st.number_input("💰 ราคา", min_value=0, value=0)

        if st.button("🚀 โพสต์เลย", use_container_width=True):
            final_img_links = [convert_drive_link(l) for l in img_links if not convert_drive_link(l).startswith("ERROR")]
            final_vid_links = [convert_drive_video_link(l) for l in vid_links if not convert_drive_video_link(l).startswith("ERROR")]
            
            if new_desc:
                img_paths = []
                if new_imgs:
                    for img_file in new_imgs:
                        fname = f"img_{int(time.time())}_{img_file.name}"
                        with open(fname, "wb") as f: f.write(img_file.getbuffer())
                        img_paths.append(fname)
                img_paths.extend(final_img_links)
                
                video_paths = []
                if new_video:
                    vname = new_video.name
                    with open(vname, "wb") as f: f.write(new_video.getbuffer())
                    video_paths.append(vname)
                video_paths.extend(final_vid_links)
                
                new_post = {
                    "id": str(datetime.datetime.now().timestamp()),
                    "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "content": new_desc,
                    "images": img_paths,
                    "video": video_paths,
                    "color": post_color,
                    "price": price,
                    "likes": 0,
                    "reactions": {'😻': 0, '🙀': 0, '😿': 0, '😾': 0, '🧠': 0},
                    "comments": []
                }
                
                myla_reply = ""
                if ai_available:
                    try:
                        prompt = f"ตอบกลับโพสต์นี้ของบอส '{new_desc}' สั้นๆ น่ารัก กวนๆ"
                        response = model.generate_content(prompt)
                        myla_reply = response.text.strip()
                    except: myla_reply = "โพสต์เท่มากค่ะบอส! 😎"
                else: myla_reply = "กดไลก์รัวๆ ให้เลยค่ะ 👍"

                new_post['comments'].append({"user": "🧚‍♀️ Myla (AI)", "text": myla_reply, "is_admin": False, "image": None})

                current = load_data()
                current.append(new_post)
                save_data(current)
                st.success("เรียบร้อย!")
                time.sleep(1); st.rerun()

    # --- Tab 2: แก้ไขโพสต์ (NEW FEATURE) ---
    with tab_edit_post:
        st.markdown("### ✏️ แก้ไขโพสต์เก่า")
        
        # โหลดโพสต์ทั้งหมดมาใส่ Selectbox
        all_posts = load_data()
        if not all_posts:
            st.warning("ไม่มีโพสต์ให้แก้ครับ")
        else:
            # สร้าง Dictionary สำหรับ Selectbox {label: post_id}
            post_options = {f"{p['date']} - {p['content'][:40]}...": p['id'] for p in reversed(all_posts)}
            selected_label = st.selectbox("เลือกโพสต์ที่จะแก้ไข:", list(post_options.keys()))
            
            if selected_label:
                selected_id = post_options[selected_label]
                # หา object โพสต์ตัวจริง
                curr_post = next((p for p in all_posts if p['id'] == selected_id), None)
                
                if curr_post:
                    with st.form(key="edit_post_form"):
                        st.caption(f"กำลังแก้ไข ID: {selected_id}")
                        
                        edit_content = st.text_area("เนื้อหาใหม่", value=curr_post.get('content', ''))
                        
                        c_edit1, c_edit2 = st.columns(2)
                        with c_edit1:
                            edit_price = st.number_input("ราคาใหม่", min_value=0, value=curr_post.get('price', 0))
                        with c_edit2:
                            edit_color = st.color_picker("สีธีมใหม่", value=curr_post.get('color', '#A370F7'))

                        st.markdown("---")
                        st.markdown("#### 🖼️ จัดการสื่อ (Media)")
                        
                        # แสดงรูปปัจจุบัน
                        curr_imgs = curr_post.get('images', [])
                        curr_vids = curr_post.get('video', [])
                        
                        if curr_imgs:
                            st.write(f"📸 มีรูปอยู่ {len(curr_imgs)} รูป")
                        if curr_vids:
                            st.write(f"🎥 มีวิดีโออยู่ {len(curr_vids)} คลิป")
                            
                        # ตัวเลือก: ลบของเก่าทั้งหมดแล้วลงใหม่
                        clear_media = st.checkbox("🗑️ ลบรูปและคลิปเก่าออกทั้งหมด (ถ้าจะเปลี่ยนใหม่)", value=False)
                        
                        st.info("➕ เพิ่มสื่อใหม่ (จะต่อท้ายของเดิม ถ้าไม่ได้ติ๊กลบ)")
                        
                        # ส่วนอัปโหลดเพิ่ม (เหมือนตอนโพสต์ใหม่)
                        add_imgs = st.file_uploader("เพิ่มรูปไฟล์", type=['png','jpg'], accept_multiple_files=True, key="edit_upl_img")
                        
                        # ลิงก์รูป (ใช้ Session State แยกสำหรับ Edit Tab)
                        st.caption("เพิ่มลิงก์รูป (สูงสุด 3 ช่อง เพื่อความง่าย)")
                        edit_img_link1 = st.text_input("Link รูป 1", key="eil1")
                        edit_img_link2 = st.text_input("Link รูป 2", key="eil2")
                        edit_img_link3 = st.text_input("Link รูป 3", key="eil3")

                        st.markdown("-")
                        add_vid = st.file_uploader("เพิ่มคลิปไฟล์", type=['mp4','mov'], key="edit_upl_vid")
                        st.caption("เพิ่มลิงก์คลิป (สูงสุด 2 ช่อง)")
                        edit_vid_link1 = st.text_input("Link คลิป 1", key="evl1")
                        edit_vid_link2 = st.text_input("Link คลิป 2", key="evl2")

                        if st.form_submit_button("💾 บันทึกการแก้ไข"):
                            # 1. อัปเดตข้อมูล Text
                            curr_post['content'] = edit_content
                            curr_post['price'] = edit_price
                            curr_post['color'] = edit_color
                            
                            # 2. จัดการ Media
                            if clear_media:
                                curr_post['images'] = []
                                curr_post['video'] = []
                            
                            # เพิ่มรูปไฟล์
                            if add_imgs:
                                for img_file in add_imgs:
                                    fname = f"img_{int(time.time())}_{img_file.name}"
                                    with open(fname, "wb") as f: f.write(img_file.getbuffer())
                                    curr_post['images'].append(fname)
                            
                            # เพิ่มรูปจากลิงก์
                            for l in [edit_img_link1, edit_img_link2, edit_img_link3]:
                                if l: curr_post['images'].append(convert_drive_link(l))
                                
                            # เพิ่มวิดีโอไฟล์
                            if add_vid:
                                vname = add_vid.name
                                with open(vname, "wb") as f: f.write(add_vid.getbuffer())
                                curr_post['video'].append(vname)
                                
                            # เพิ่มวิดีโอจากลิงก์
                            for l in [edit_vid_link1, edit_vid_link2]:
                                if l: curr_post['video'].append(convert_drive_video_link(l))

                            # 3. บันทึกกลับ
                            # หา Index ของโพสต์นี้ใน List ใหญ่แล้วแทนที่
                            for i, p in enumerate(all_posts):
                                if p['id'] == selected_id:
                                    all_posts[i] = curr_post
                                    break
                            
                            save_data(all_posts)
                            st.success("แก้ไขโพสต์เรียบร้อยครับบอส!")
                            time.sleep(1.5)
                            st.rerun()

    # --- Tab 3: แก้ไขโปรไฟล์ ---
    with tab_profile:
        st.markdown("### 📢 จัดการป้ายไฟ (Billboard)")
        bb_text = st.text_input("ข้อความบนป้ายไฟ", value=profile_data.get('billboard', {}).get('text', ''))
        c_bb1, c_bb2 = st.columns(2)
        with c_bb1:
            if st.button("บันทึกป้ายไฟ"):
                profile_data['billboard'] = {'text': bb_text, 'timestamp': datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}
                save_profile(profile_data)
                st.success("อัปเดตป้ายไฟแล้ว!")
                st.rerun()
        with c_bb2:
            if st.button("ลบป้ายไฟ", type="primary"):
                profile_data['billboard'] = {'text': '', 'timestamp': ''}
                save_profile(profile_data)
                st.rerun()
        
        st.markdown("---")
        with st.form("pf_form"):
            p_name = st.text_input("ชื่อ", value=profile_data.get('name', 'Dearluxion'))
            p_emoji = st.text_input("อิโมจิประจำตัว", value=profile_data.get('emoji', '😎'))
            p_status = st.text_input("Status", value=profile_data.get('status', 'ว่างงาน...'))
            p_bio = st.text_input("Bio", value=profile_data.get('bio', ''))
            p_discord = st.text_input("Discord URL", value=profile_data.get('discord',''))
            p_ig = st.text_input("IG URL", value=profile_data.get('ig',''))
            p_ex = st.text_area("ลิงก์อื่นๆ", value=profile_data.get('extras',''))
            
            if st.form_submit_button("บันทึกข้อมูลส่วนตัว"):
                profile_data.update({
                    "name": p_name, "emoji": p_emoji, "status": p_status, "bio": p_bio, 
                    "discord": p_discord, "ig": p_ig, "extras": p_ex
                })
                save_profile(profile_data)
                st.success("อัปเดตแล้ว!")
                st.rerun()
            
    with tab_inbox:
        st.markdown("### 💌 จดหมายลับ")
        msgs = load_mailbox()
        if msgs:
            if st.button("ลบจดหมายทั้งหมด"):
                if os.path.exists(MAILBOX_FILE): os.remove(MAILBOX_FILE)
                st.rerun()
            for m in reversed(msgs):
                st.info(f"📅 **{m['date']}**: {m['text']}")
        else: st.info("ยังไม่มีจดหมายลับ")
            
    st.markdown("---")

# --- 6. Feed Display ---
filtered = posts
if st.session_state['show_shop']:
    st.markdown("## 🛒 ร้านค้า (Shop Zone)")
    with st.expander("🧚‍♀️ พี่จ๋า~ หาทางกลับไม่เจอเหรอคะ?", expanded=True):
        st.markdown("""<div class="cute-guide">✨ ทางลัดพิเศษสำหรับพี่คนโปรดของไมล่า! 🌈</div>""", unsafe_allow_html=True)
        if st.button("🏠 กลับบ้านกับไมล่า!", use_container_width=True):
            st.session_state['show_shop'] = False
            st.balloons(); time.sleep(1); st.rerun()
    filtered = [p for p in filtered if p.get('price', 0) > 0 or "#ร้านค้า" in p['content']]
    if not filtered: st.warning("ยังไม่มีสินค้าวางขายจ้า")
else:
    if selected_zone != "🏠 รวมทุกโซน": filtered = [p for p in filtered if selected_zone in p['content']]
    if search_query: filtered = [p for p in filtered if search_query.lower() in p['content'].lower()]

if filtered:
    for post in reversed(filtered):
        accent = post.get('color', '#A370F7')
        if 'reactions' not in post: post['reactions'] = {'😻': 0, '🙀': 0, '😿': 0, '😾': 0, '🧠': 0}
        
        with st.container():
            col_head, col_del = st.columns([0.85, 0.15])
            with col_head:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
                    <div style="font-size:40px; line-height:1; filter: drop-shadow(0 0 5px {accent});">{user_emoji}</div>
                    <div style="line-height:1.2;">
                        <div style="font-size:18px; font-weight:bold; color:#E6EDF3;">
                            {profile_data.get('name', 'Dearluxion')} 
                            <span style="color:{accent}; font-size:14px;">🛡️ Verified</span>
                        </div>
                        <div style="font-size:12px; color:#8B949E;">{post['date']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_del:
                if st.session_state['is_admin']:
                    if st.button("🗑️", key=f"del_{post['id']}"):
                        all_p = load_data()
                        save_data([x for x in all_p if x['id'] != post['id']])
                        st.rerun()

            if post.get('image') and os.path.exists(post['image']): 
                st.image(post['image'], use_container_width=True)
            
            if post.get('images'):
                valid_imgs = [img for img in post['images'] if img.startswith("http") or os.path.exists(img)]
                if valid_imgs:
                    if len(valid_imgs) == 1: st.image(valid_imgs[0], use_container_width=True)
                    else:
                        img_cols = st.columns(3)
                        for idx, img in enumerate(valid_imgs):
                            with img_cols[idx % 3]: st.image(img, use_container_width=True)

            videos = post.get('video')
            if videos:
                if isinstance(videos, str): videos = [videos]
                for vid in videos:
                    if "drive.google.com" in vid and "preview" in vid:
                         st.markdown(f'<iframe src="{vid}" width="100%" height="300" style="border:none; border-radius:10px;"></iframe>', unsafe_allow_html=True)
                    elif vid.startswith("http") or os.path.exists(vid): st.video(vid)
            
            content = post['content']
            yt = re.search(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})', content)
            if yt: st.video(f"https://youtu.be/{yt.group(6)}")
            
            st.markdown(f"""<div class="work-card-base" style="border-left: 5px solid {accent};">{content}</div>""", unsafe_allow_html=True)
            
            price = post.get('price', 0)
            if price > 0:
                st.markdown(f"<div class='price-tag'>💰 ราคา: {price:,} บาท</div>", unsafe_allow_html=True)
                buy_link = profile_data.get('ig') or profile_data.get('discord') or "#"
                st.markdown(f"""<a href="{buy_link}" target="_blank"><button style="background-color:{accent}; color:white; border:none; padding:8px 16px; border-radius:8px; width:100%; cursor:pointer;">🛍️ สนใจสั่งซื้อ (คลิก)</button></a><br><br>""", unsafe_allow_html=True)

            st.write("---")
            rx_cols = st.columns(5)
            emojis = ['😻', '🙀', '😿', '😾', '🧠']
            user_react = st.session_state['user_reactions'].get(post['id'])

            for i, emo in enumerate(emojis):
                with rx_cols[i]:
                    count = post['reactions'].get(emo, 0)
                    if st.button(f"{emo} {count}", key=f"react_{post['id']}_{i}", type="primary" if user_react == emo else "secondary"):
                        d = load_data()
                        for p in d:
                            if p['id'] == post['id']:
                                if 'reactions' not in p: p['reactions'] = {'😻': 0, '🙀': 0, '😿': 0, '😾': 0, '🧠': 0}
                                if user_react == emo:
                                    p['reactions'][emo] = max(0, p['reactions'][emo] - 1)
                                    del st.session_state['user_reactions'][post['id']]
                                else:
                                    if user_react and user_react in p['reactions']: p['reactions'][user_react] = max(0, p['reactions'][user_react] - 1)
                                    p['reactions'][emo] += 1
                                    st.session_state['user_reactions'][post['id']] = emo
                                    if emo == '😻': st.balloons()
                                break
                        save_data(d)
                        time.sleep(0.5); st.rerun()

            with st.expander(f"💬 ความคิดเห็น ({len(post['comments'])})"):
                if post['comments']:
                    for i, c in enumerate(post['comments']):
                        is_admin_comment = c.get('is_admin', False)
                        if is_admin_comment:
                            st.markdown(f"""<div class='admin-comment-box'><b>👑 {c['user']} (Owner):</b> {c['text']}</div>""", unsafe_allow_html=True)
                            if c.get('image') and os.path.exists(c['image']): st.image(c['image'], width=200)
                        else:
                            st.markdown(f"<div class='comment-box'><b>{c['user']}:</b> {c['text']}</div>", unsafe_allow_html=True)
                        
                        if st.session_state['is_admin'] and st.button("ลบ", key=f"dc_{post['id']}_{i}"):
                            d = load_data()
                            for x in d:
                                if x['id'] == post['id']: x['comments'].pop(i); break
                            save_data(d); st.rerun()
                
                admin_cmt_img = None
                if st.session_state['is_admin']:
                    st.caption("👑 ตอบกลับในฐานะ Admin")
                    admin_cmt_img = st.file_uploader("แนบรูป", type=['png','jpg'], key=f"ci_{post['id']}")

                with st.form(key=f"cf_{post['id']}"):
                    u = st.text_input("ชื่อ", placeholder="ชื่อเล่น...", label_visibility="collapsed") if not st.session_state['is_admin'] else "Dearluxion"
                    t = st.text_input("ข้อความ", placeholder="แสดงความคิดเห็น...", label_visibility="collapsed")
                    
                    if st.form_submit_button("ส่ง"):
                        now = time.time()
                        if not st.session_state['is_admin'] and now - st.session_state['last_comment_time'] < 35:
                            st.toast(f"รออีก {35 - int(now - st.session_state['last_comment_time'])} วิ นะ!", icon="⛔")
                        elif t:
                            cmt_img_path = None
                            if admin_cmt_img:
                                cmt_img_path = f"cmt_{int(now)}_{admin_cmt_img.name}"
                                with open(cmt_img_path, "wb") as f: f.write(admin_cmt_img.getbuffer())

                            d = load_data()
                            for x in d:
                                if x['id'] == post['id']: 
                                    x['comments'].append({"user": u if u else "Guest", "text": t, "is_admin": st.session_state['is_admin'], "image": cmt_img_path})
                                    break
                            save_data(d)
                            if not st.session_state['is_admin']: st.session_state['last_comment_time'] = now
                            st.rerun()
else:
    if not st.session_state['show_shop']: st.info("ยังไม่มีโพสต์ครับ")

st.markdown("<br><center><small style='color:#A370F7'>Small Group by Dearluxion © 2025</small></center>", unsafe_allow_html=True)