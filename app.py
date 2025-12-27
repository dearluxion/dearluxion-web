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

# --- 0. ตั้งค่า API KEY ---
# (ดึงจาก Secrets ก่อน ถ้าไม่มีค่อยใช้ตัว Hardcode)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# Config Gemini
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
        if "/folders/" in link: return "ERROR: ห้ามใช้ลิงก์ Folder!"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match: return f'https://lh3.googleusercontent.com/d/{match.group(1)}'
    return link 

def convert_drive_video_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link: return "ERROR: ห้ามใช้ลิงก์ Folder!"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match: return f'https://drive.google.com/file/d/{match.group(1)}/preview'
    return link

# --- [CORE] ระบบ Database (เชื่อมต่อ Google Sheets) ---
DB_FILE = "portfolio_db.json"
PROFILE_FILE = "profile_db.json"
MAILBOX_FILE = "mailbox_db.json"

def get_gsheet_client():
    if not has_gspread: return None
    if "gcp_service_account" not in st.secrets: return None
    try:
        # --- 🛠️ ส่วนซ่อมกุญแจ (สำคัญมาก!) ---
        key_dict = dict(st.secrets["gcp_service_account"])
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        # -----------------------------------
        
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        # ใช้ชื่อไฟล์จาก secrets หรือ default 'streamlit_db'
        sheet_name = st.secrets.get("sheet_name", "streamlit_db")
        return client.open(sheet_name)
    except Exception as e:
        return None

# --- Override: Load Data ---
def load_data():
    # 1. ลองโหลดจาก Google Sheets
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
    
    # 2. Fallback: ไฟล์เดิม
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

# --- Override: Save Data ---
def save_data(data):
    # 1. บันทึกลง Google Sheets
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
            st.error(f"บันทึก Sheets ไม่ได้: {e}")

    # 2. บันทึกลงไฟล์สำรอง
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

# --- Override: Load Profile ---
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
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

# --- Override: Save Profile ---
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
        
    try:
        with open(PROFILE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

# --- Override: Load Mailbox ---
def load_mailbox():
    sh = get_gsheet_client()
    if sh:
        try: return sh.worksheet("mailbox").get_all_records()
        except: pass
        
    if not os.path.exists(MAILBOX_FILE): return []
    try:
        with open(MAILBOX_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

# --- Override: Save Mailbox ---
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
        
    try:
        with open(MAILBOX_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

# --- Session & Init ---
if 'liked_posts' not in st.session_state: st.session_state['liked_posts'] = []
if 'user_reactions' not in st.session_state: st.session_state['user_reactions'] = {}
for k in ['last_comment_time','last_fortune_time','last_gossip_time','last_mailbox_time','last_choice_time','last_stock_trade']:
    if k not in st.session_state: st.session_state[k] = 0
if 'show_shop' not in st.session_state: st.session_state['show_shop'] = False
if 'is_admin' not in st.session_state: st.session_state['is_admin'] = False
if 'num_img_links' not in st.session_state: st.session_state['num_img_links'] = 1
if 'num_vid_links' not in st.session_state: st.session_state['num_vid_links'] = 1

# Tokens
if 'feed_tokens' not in st.session_state: st.session_state['feed_tokens'] = 5
if 'last_token_regen' not in st.session_state: st.session_state['last_token_regen'] = time.time()
if 'feed_msg' not in st.session_state: st.session_state['feed_msg'] = None
if 'bar_tokens' not in st.session_state: st.session_state['bar_tokens'] = 5
if 'last_bar_regen' not in st.session_state: st.session_state['last_bar_regen'] = time.time()
if 'bar_result' not in st.session_state: st.session_state['bar_result'] = None

now = time.time()
if now - st.session_state['last_token_regen'] >= 60:
    st.session_state['feed_tokens'] = min(5, st.session_state['feed_tokens'] + int((now - st.session_state['last_token_regen'])//60))
    st.session_state['last_token_regen'] = now
if now - st.session_state['last_bar_regen'] >= 3600:
    st.session_state['bar_tokens'] = min(5, st.session_state['bar_tokens'] + int((now - st.session_state['last_bar_regen'])//3600))
    st.session_state['last_bar_regen'] = now

# --- 3. Sidebar (เมนูเดิมครบชุด) ---
st.sidebar.title("🍸 เมนูหลัก")

# Q&A
with st.sidebar.expander("🧚‍♀️ ถาม-ตอบ กับไมล่า (Q&A)", expanded=True):
    st.markdown("### 💬 อยากรู้อะไรถามไมล่าได้เลย!")
    q_options = ["เลือกคำถาม...", "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?", "🛍️ สนใจสินค้า ซื้อยังไง?", "💻 เว็บนี้ใครสร้างครับ?", "🧚‍♀️ ไมล่าคือใครคะ?", "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?", "🐍 รู้หรือไม่? เว็บนี้ใช้ Python กี่ตัวอักษร?", "🤖 บอสใช้ AI ตัวไหนทำงาน?", "🍕 บอสชอบกินอะไรที่สุด?"]
    selected_q = st.selectbox("เลือกคำถาม:", q_options, label_visibility="collapsed")
    if selected_q == "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?": st.info("🧚‍♀️ **ไมล่า:** ไม่ได้น้า~ นี่เป็น **พื้นที่ส่วนตัวของบอส Dearluxion** เท่านั้นค่ะ!")
    elif selected_q == "🛍️ สนใจสินค้า ซื้อยังไง?": st.success("🧚‍♀️ **ไมล่า:** กดปุ่ม **'สนใจสั่งซื้อ'** ในโพสต์ขายของเลยค่ะ!")
    elif selected_q == "💻 เว็บนี้ใครสร้างครับ?": st.warning("🧚‍♀️ **ไมล่า:** **ท่าน Dearluxion สร้างเองกับมือ** ด้วยภาษา Python ล้วนๆ ค่ะ!")
    elif selected_q == "🧚‍♀️ ไมล่าคือใครคะ?": st.markdown("""<div style="background-color:#161B22; padding:15px; border-radius:10px; border:1px solid #A370F7;">หนูคือไมล่า AI ผู้ช่วยบอสค่ะ!</div>""", unsafe_allow_html=True)
    elif selected_q == "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?": st.error("🧚‍♀️ **ไมล่า:** จิ้มที่ลิงก์ Discord หรือ IG ตรงหน้าโปรไฟล์ด้านบนได้เลยค่ะ")
    elif selected_q == "🐍 รู้หรือไม่? เว็บนี้ใช้ Python กี่ตัวอักษร?": st.info("🧚‍♀️ **ไมล่า:** มากกว่า **47,828 ตัวอักษร** แล้วค่ะ!")
    elif selected_q == "🤖 บอสใช้ AI ตัวไหนทำงาน?": st.success("🧚‍♀️ **ไมล่า:** เบื้องหลังคือ **Google Gemini 2.5** ค่ะ")
    elif selected_q == "🍕 บอสชอบกินอะไรที่สุด?": st.warning("🧚‍♀️ **ไมล่า:** บอสชอบกิน **ปลาส้ม (Salmon)** ที่สุดค่ะ!")

# Gossip
with st.sidebar.expander("🤫 มุมนินทาบอส (Myla's Gossip)"):
    if st.button("ความลับของบอส... 💬"):
        if now - st.session_state['last_gossip_time'] < 5: st.warning("⚠️ อย่ากดรัวสิคะ!")
        else:
            gossips = ["เมื่อคืนบอสเปิดเพลงเศร้าวนไป 10 รอบเลย...", "บอสบอกว่าจะลดความอ้วน แต่กินชาไข่มุกอีกแล้ว!", "บอสแอบส่องไอจีใครบางคนทุกวันเลยแหละ...", "เห็นบอสเข้มๆ แบบนี้ จริงๆ ขี้เหงามากนะ", "บอสชอบแมวแต่แมวไม่รัก..."]
            st.toast(f"🧚‍♀️ ไมล่าแอบบอก: {random.choice(gossips)}", icon="🤫")
            st.session_state['last_gossip_time'] = now

st.sidebar.markdown("---")

# Myla's Choice
with st.sidebar.expander("⚖️ Myla's Choice (ที่ปรึกษาหัวใจ)"):
    choice_topic = st.selectbox("เรื่องที่หนักใจ...", ["เลือกหัวข้อ...", "📲 ทักเขาไปตอนนี้ดีไหม?", "💔 เขายังคิดถึงเราอยู่รึเปล่า?", "🔙 ถ้ากลับไป... จะดีกว่าเดิมไหม?", "⏳ ควรรอต่อไป หรือ พอแค่นี้?"])
    if st.button("ขอคำตอบฟันธง! ⚡"):
        if now - st.session_state['last_choice_time'] < 15: st.warning(f"⏳ ใจเย็นๆ ค่ะ รออีก {15 - int(now - st.session_state['last_choice_time'])} วิ")
        elif choice_topic == "เลือกหัวข้อ...": st.warning("เลือกคำถามก่อนสิคะ!")
        else:
            answers = ["ทักเลย!", "อย่าฟอร์มเยอะ!", "รออีกนิด!", "มูฟออนเถอะ!", "เขาคิดถึงคุณอยู่!", "เชื่อในสัญชาตญาณ!"]
            st.toast(f"🧚‍♀️ ไมล่าฟันธง: {random.choice(answers)}", icon="💘")
            st.session_state['last_choice_time'] = now

st.sidebar.markdown("---")

# Treat Me
with st.sidebar.expander("🥤 Treat Me (เลี้ยงอาหารทิพย์)", expanded=True):
    pf_stats = load_profile()
    if 'treats' not in pf_stats: pf_stats['treats'] = {}
    if 'top_feeders' not in pf_stats: pf_stats['top_feeders'] = {}
    tokens = st.session_state['feed_tokens']
    
    st.markdown(f"<small>พลังงานการเปย์: {tokens}/5 ⚡</small>", unsafe_allow_html=True)
    feeder_name = st.text_input("ชื่อคนใจดี:", placeholder="ใส่ชื่อเล่น...", key="feeder_name")
    if st.session_state.get('feed_msg'):
        st.success(st.session_state['feed_msg'])
        st.balloons()
        st.session_state['feed_msg'] = None

    def feed_boss(item_name):
        if st.session_state['feed_tokens'] > 0:
            st.session_state['feed_tokens'] -= 1
            st.session_state['feed_msg'] = f"😎 บอส: ขอบคุณสำหรับ {item_name} ค้าบ! (จาก: {feeder_name if feeder_name else 'FC'})"
            pf = load_profile()
            if 'treats' not in pf: pf['treats'] = {}
            if 'top_feeders' not in pf: pf['top_feeders'] = {}
            pf['treats'][item_name] = pf['treats'].get(item_name, 0) + 1
            if feeder_name: pf['top_feeders'][feeder_name] = pf['top_feeders'].get(feeder_name, 0) + 1
            save_profile(pf)
            st.rerun()
        else: st.toast("🧚‍♀️ ไมล่า: บอสอิ่มแล้ว... รอระบบย่อยแป๊บนึงนะ!", icon="⛔")

    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button(f"🐟 {pf_stats['treats'].get('ปลาส้มทอด 🐟',0)}"): feed_boss("ปลาส้มทอด 🐟")
        if st.button(f"☕ {pf_stats['treats'].get('กาแฟลาเต้ ☕',0)}"): feed_boss("กาแฟลาเต้ ☕")
    with c2:
        if st.button(f"🍣 {pf_stats['treats'].get('ซูชิ 🍣',0)}"): feed_boss("ซูชิ 🍣")
        if st.button(f"🧋 {pf_stats['treats'].get('ชาไทย 🧋',0)}"): feed_boss("ชาไทย 🧋")
    with c3:
        if st.button(f"🍔 {pf_stats['treats'].get('เบอร์เกอร์ 🍔',0)}"): feed_boss("เบอร์เกอร์ 🍔")
        if st.button(f"🍕 {pf_stats['treats'].get('พิซซ่า 🍕',0)}"): feed_boss("พิซซ่า 🍕")

# Hall of Fame
if 'top_feeders' in pf_stats and pf_stats['top_feeders']:
    with st.sidebar.expander("🏆 ทำเนียบสายเปย์"):
        sorted_feeders = sorted(pf_stats['top_feeders'].items(), key=lambda x: x[1], reverse=True)[:5]
        for idx, (name, score) in enumerate(sorted_feeders):
            st.markdown(f"{idx+1}. **{name}** — {score} ครั้ง")

st.sidebar.markdown("---")

# Stock Market
with st.sidebar.expander("📈 Love Stock Market", expanded=True):
    pf = load_profile()
    if 'stock' not in pf: pf['stock'] = {'price': 100.0, 'history': [100.0]}
    price = pf['stock']['price']
    st.metric("ราคาหุ้นความฮอต 🔥", f"{price:.2f} Pts")
    st.line_chart(pf['stock']['history'][-20:])
    
    on_cooldown = time.time() - st.session_state['last_stock_trade'] < 1800
    b1, b2 = st.columns(2)
    if b1.button("🟢 ช้อนซื้อ"):
        if on_cooldown: st.warning("⏳ ตลาดพักการซื้อขาย!")
        else:
            pf['stock']['price'] += random.uniform(0.5, 5.0)
            pf['stock']['history'].append(pf['stock']['price'])
            save_profile(pf)
            st.session_state['last_stock_trade'] = time.time()
            st.toast("หุ้นพุ่ง!", icon="📈"); st.rerun()
    if b2.button("🔴 เทขาย"):
        if on_cooldown: st.warning("⏳ ตลาดพักการซื้อขาย!")
        else:
            pf['stock']['price'] = max(0, pf['stock']['price'] - random.uniform(0.5, 5.0))
            pf['stock']['history'].append(pf['stock']['price'])
            save_profile(pf)
            st.session_state['last_stock_trade'] = time.time()
            st.toast("หุ้นร่วง!", icon="📉"); st.rerun()

st.sidebar.markdown("---")

# Bar & Fortune & Mailbox
with st.sidebar.expander("🍸 Mood Mocktail"):
    user_mood = st.text_area("อารมณ์วันนี้:", placeholder="เหนื่อย, เหงา...")
    if st.button("🥃 ชงเลย"):
        if bar_tokens > 0 and user_mood:
            with st.spinner("⏳ กำลังชง..."):
                try:
                    res = model.generate_content(f"เป็นบาร์เทนเดอร์ AI คิดสูตร Mocktail จากอารมณ์: {user_mood} ตอบสั้นๆ")
                    st.session_state['bar_result'] = res.text; st.session_state['bar_tokens'] -= 1; st.rerun()
                except: st.error("AI เมาค้าง")
        else: st.warning("โควต้าหมด หรือ ลืมใส่อารมณ์")
    if st.session_state.get('bar_result'): st.success(st.session_state['bar_result'])

with st.sidebar.expander("🔮 เซียมซี"):
    if st.button("เสี่ยงทาย"):
        if now - st.session_state['last_fortune_time'] < 3600: st.warning("รอคูลดาวน์!")
        else:
            st.toast(f"คำทำนาย: {random.choice(['สมหวัง!', 'รออีกนิด', 'ระวังคนใกล้ตัว'])}", icon="🔮")
            st.session_state['last_fortune_time'] = now

with st.sidebar.expander("💌 ตู้จดหมายลับ"):
    msg = st.text_area("ข้อความถึงบอส:")
    if st.button("ส่งความลับ"):
        if now - st.session_state['last_mailbox_time'] < 3600: st.warning("ส่งบ่อยไป!")
        elif msg:
            ms = load_mailbox()
            ms.append({"date": datetime.datetime.now().strftime("%d/%m %H:%M"), "text": msg})
            save_mailbox(ms)
            st.session_state['last_mailbox_time'] = now
            st.success("ส่งแล้ว!")

st.sidebar.markdown("---")
search_query = st.sidebar.text_input("🔍 ค้นหา...")
if st.session_state['show_shop']:
    st.sidebar.info("🛒 อยู่ในร้านค้า"); 
    if st.sidebar.button("🏠 กลับหน้าหลัก"): st.session_state['show_shop'] = False; st.rerun()
else:
    all_tags = set()
    posts = load_data()
    for p in posts:
        for t in re.findall(r"#(\w+)", p.get('content','')): all_tags.add(f"#{t}")
    selected_zone = st.sidebar.radio("หมวดหมู่:", ["🏠 รวมทุกโซน"] + sorted(list(all_tags)))

# --- LOGIN ---
if not st.session_state['is_admin']:
    with st.sidebar.expander("🔐 Login"):
        u = st.text_input("ID"); p = st.text_input("PW", type="password")
        if st.button("ไขกุญแจ"):
            if u == "dearluxion" and p == "1212312121mc": st.session_state['is_admin'] = True; st.rerun()
            else: st.error("ผิด!")
else: st.sidebar.success("Welcome Boss!"); st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'is_admin':False}))

# --- MAIN CONTENT ---
profile = load_profile()
if not st.session_state['is_admin']:
    hour = datetime.datetime.now().hour
    st.info(f"🧚‍♀️ **ไมล่า:** สวัสดีตอน{'เช้า' if 5<=hour<12 else 'บ่าย' if 12<=hour<18 else 'ค่ำ'}ค่ะพี่จ๋า~")

c_p1, c_p2 = st.columns([1.5, 6])
c_p1.markdown(f"<div style='font-size:60px; text-align:center;'>{profile.get('emoji','😎')}</div>", unsafe_allow_html=True)
c_p2.markdown(f"### 🍸 {profile.get('name','Dearluxion')}\n_{profile.get('bio','...')}_ \n\n💬 Status: `{profile.get('status','...')}`")
if st.button("🛒", help="ไปช้อปปิ้ง"): st.session_state['show_shop'] = True; st.rerun()

if profile.get('billboard',{}).get('text'):
    st.markdown(f"""<div class='boss-billboard'><div class='billboard-text'>{profile['billboard']['text']}</div></div>""", unsafe_allow_html=True)

# --- ADMIN PANEL ---
if st.session_state['is_admin']:
    tab1, tab2, tab3 = st.tabs(["📝 เขียน/ขาย", "👤 โปรไฟล์", "📬 กล่องจดหมาย"])
    
    with tab1:
        new_desc = st.text_area("เนื้อหา Story")
        
        # Multiple Image Links
        st.caption("📷 ลิงก์รูป (Google Drive/Web)")
        c_i1, c_i2 = st.columns([1,1])
        if c_i1.button("➕ เพิ่มช่องรูป"): st.session_state['num_img_links'] += 1
        if c_i2.button("➖ ลดช่องรูป") and st.session_state['num_img_links'] > 1: st.session_state['num_img_links'] -= 1
        
        img_links = []
        for i in range(st.session_state['num_img_links']):
            l = st.text_input(f"Link รูปที่ {i+1}", key=f"img_{i}")
            if l: img_links.append(l)
            
        # Multiple Video Links
        st.markdown("---")
        st.caption("🎥 ลิงก์วิดีโอ (Google Drive)")
        c_v1, c_v2 = st.columns([1,1])
        if c_v1.button("➕ เพิ่มช่องคลิป"): st.session_state['num_vid_links'] += 1
        if c_v2.button("➖ ลดช่องคลิป") and st.session_state['num_vid_links'] > 1: st.session_state['num_vid_links'] -= 1
        
        vid_links = []
        for i in range(st.session_state['num_vid_links']):
            l = st.text_input(f"Link คลิปที่ {i+1}", key=f"vid_{i}")
            if l: vid_links.append(l)
            
        col_c, col_p = st.columns(2)
        p_color = col_c.color_picker("สีธีม", "#A370F7")
        price = col_p.number_input("ราคา", 0)
        
        if st.button("🚀 โพสต์เลย"):
            # Process Links
            final_imgs = []
            for l in img_links:
                conv = convert_drive_link(l.strip())
                if "ERROR" in conv: st.error(conv); st.stop()
                final_imgs.append(conv)
                
            final_vids = []
            for l in vid_links:
                conv = convert_drive_video_link(l.strip())
                if "ERROR" in conv: st.error(conv); st.stop()
                final_vids.append(conv)
            
            new_post = {
                "id": str(int(time.time())),
                "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                "content": new_desc,
                "images": final_imgs,
                "video": final_vids,
                "color": p_color, "price": price,
                "reactions": {'😻':0,'🙀':0,'😿':0,'😾':0,'🧠':0},
                "comments": []
            }
            
            # Myla Auto-Reply
            try:
                if ai_available:
                    res = model.generate_content(f"ไมล่าตอบบอสที่โพสต์ว่า: {new_desc}")
                    reply = res.text.strip()
                else: reply = "สุดยอดค่ะบอส! 😎"
            except: reply = "เท่มากค่ะ!"
            
            new_post['comments'].append({"user": "🧚‍♀️ Myla", "text": reply, "is_admin": False})
            
            curr = load_data()
            curr.append(new_post)
            save_data(curr)
            st.success("เรียบร้อย! (บันทึกลง Sheets แล้ว)")
            st.session_state['num_img_links'] = 1; st.session_state['num_vid_links'] = 1
            time.sleep(1); st.rerun()

    with tab2:
        with st.form("pf_edit"):
            pn = st.text_input("ชื่อ", profile.get('name',''))
            pb = st.text_input("Bio", profile.get('bio',''))
            ps = st.text_input("Status", profile.get('status',''))
            bb = st.text_input("Billboard Text", profile.get('billboard',{}).get('text',''))
            if st.form_submit_button("บันทึก"):
                profile.update({'name':pn, 'bio':pb, 'status':ps, 'billboard':{'text':bb, 'timestamp':''}})
                save_profile(profile); st.rerun()
                
    with tab3:
        if st.button("ลบจดหมายทั้งหมด"): save_mailbox([]); st.rerun()
        for m in reversed(load_mailbox()): st.info(f"{m['date']}: {m['text']}")

st.markdown("---")

# --- FEED ---
posts = load_data()
filtered = posts
if st.session_state['show_shop']:
    st.title("🛒 Shop Zone")
    filtered = [p for p in posts if p.get('price',0) > 0 or "#ร้านค้า" in p.get('content','')]
else:
    if search_query: filtered = [p for p in posts if search_query.lower() in p['content'].lower()]
    elif selected_zone != "🏠 รวมทุกโซน": filtered = [p for p in posts if selected_zone.replace("#","") in p['content']]

if filtered:
    for p in reversed(filtered):
        accent = p.get('color', '#A370F7')
        with st.container():
            c_h, c_d = st.columns([0.9, 0.1])
            c_h.markdown(f"**{profile.get('name','Dearluxion')}** <span style='color:{accent}'>Verified</span> <small>{p['date']}</small>", unsafe_allow_html=True)
            if st.session_state['is_admin'] and c_d.button("🗑️", key=f"del_{p['id']}"):
                save_data([x for x in posts if str(x['id']) != str(p['id'])]); st.rerun()
            
            # Images
            if p.get('images'):
                cols = st.columns(min(3, len(p['images'])))
                for idx, img in enumerate(p['images']): cols[idx%3].image(img, use_container_width=True)
            
            # Videos (Drive Iframe)
            if p.get('video'):
                for v in p['video']:
                    if "drive.google.com" in v and "preview" in v:
                        st.markdown(f'<iframe src="{v}" width="100%" height="320" style="border-radius:10px; border:none;"></iframe>', unsafe_allow_html=True)
                    else: st.video(v)
            
            st.markdown(f"<div class='work-card-base' style='border-left:5px solid {accent}'>{p['content']}</div>", unsafe_allow_html=True)
            
            if p.get('price',0) > 0:
                st.markdown(f"<div class='price-tag'>💰 {p['price']:,} THB</div>", unsafe_allow_html=True)
                st.markdown(f"<a href='#'><button>🛍️ สั่งซื้อ</button></a>", unsafe_allow_html=True)
            
            # Reactions
            rc = st.columns(5)
            emojis = ['😻','🙀','😿','😾','🧠']
            my_react = st.session_state['user_reactions'].get(p['id'])
            for i, e in enumerate(emojis):
                cnt = p['reactions'].get(e,0)
                if rc[i].button(f"{e} {cnt}", key=f"r_{p['id']}_{i}", type="primary" if my_react==e else "secondary"):
                    # Update Logic
                    all_p = load_data()
                    for x in all_p:
                        if str(x['id']) == str(p['id']):
                            if my_react == e: x['reactions'][e] -= 1; del st.session_state['user_reactions'][p['id']]
                            else:
                                if my_react: x['reactions'][my_react] -= 1
                                x['reactions'][e] += 1; st.session_state['user_reactions'][p['id']] = e
                            break
                    save_data(all_p); time.sleep(0.5); st.rerun()

            # Comments
            with st.expander(f"💬 คอมเมนต์ ({len(p.get('comments',[]))})"):
                for cm in p.get('comments',[]):
                    st.markdown(f"<div class='{'admin-comment-box' if cm.get('is_admin') else 'comment-box'}'><b>{cm['user']}:</b> {cm['text']}</div>", unsafe_allow_html=True)
                
                with st.form(key=f"cmt_{p['id']}"):
                    u_name = "Dearluxion" if st.session_state['is_admin'] else st.text_input("ชื่อ", placeholder="Guest")
                    txt = st.text_input("ข้อความ")
                    if st.form_submit_button("ส่ง"):
                        if txt:
                            all_p = load_data()
                            for x in all_p:
                                if str(x['id']) == str(p['id']):
                                    x['comments'].append({"user": u_name if u_name else "Guest", "text": txt, "is_admin": st.session_state['is_admin']})
                                    break
                            save_data(all_p); st.rerun()
        st.markdown("---")
else: st.info("ยังไม่มีโพสต์ (หรือ Database เชื่อมต่อไม่ได้)")

st.markdown("<center><small>Small Group by Dearluxion © 2025</small></center>", unsafe_allow_html=True)