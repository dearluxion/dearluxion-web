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
# (ดึงจาก Secrets อัตโนมัติถ้ามี หรือใช้ค่า default)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "AIzaSyAt2dJJyD45eI6n3AEq_tID3IISl2_MDfI")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') 
    ai_available = True
except:
    ai_available = False

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Small Group by Dearluxion", page_icon="🍸", layout="centered")

# CSS
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E6EDF3; font-family: 'Sarabun', sans-serif; }
    .work-card-base { background: #161B22; padding: 20px; border-radius: 15px; border: 1px solid rgba(163, 112, 247, 0.3); margin-bottom: 20px; transition: 0.3s; }
    .work-card-base:hover { transform: translateY(-2px); border-color: #A370F7; box-shadow: 0 5px 15px rgba(163, 112, 247, 0.2); }
    .stButton>button { border-radius: 25px; width: 100%; border: 1px solid #30363D; background:#21262D; color:white; }
    .stButton>button:hover { border-color: #A370F7; color: #A370F7; }
    a { color: #A370F7 !important; text-decoration: none; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- Functions แปลงลิงก์ ---
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

# --- [CORE] ระบบ Database (Google Sheets + Fix Key) ---
DB_FILE = "portfolio_db.json"
PROFILE_FILE = "profile_db.json"
MAILBOX_FILE = "mailbox_db.json"

def get_gsheet_client():
    if not has_gspread: return None
    if "gcp_service_account" not in st.secrets: return None
    try:
        # --- 🛠️ ส่วนซ่อมกุญแจ (Magic Fix) ---
        # สร้าง dict ใหม่เพื่อไม่กระทบข้อมูลเดิม
        key_dict = dict(st.secrets["gcp_service_account"])
        # เปลี่ยนตัวอักษร \n ให้เป็น Enter จริงๆ
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        # -----------------------------------

        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client.open(st.secrets.get("sheet_name", "streamlit_db"))
    except Exception as e:
        # print(f"Sheet Connect Error: {e}") # (เอาไว้ดู Log หลังบ้าน)
        return None

# --- LOAD DATA ---
def load_data():
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            records = ws.get_all_records()
            clean = []
            for r in records:
                if not str(r['id']): continue
                try:
                    r['images'] = json.loads(r['images']) if r['images'] else []
                    r['video'] = json.loads(r['video']) if r['video'] else []
                    r['reactions'] = json.loads(r['reactions']) if r['reactions'] else {'😻':0,'🙀':0,'😿':0,'😾':0,'🧠':0}
                    r['comments'] = json.loads(r['comments']) if r['comments'] else []
                    clean.append(r)
                except: continue
            return clean
        except: pass
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return []

# --- SAVE DATA ---
def save_data(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            # เรียงลำดับคอลัมน์ให้ตรงกับ Google Sheets
            rows = [["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"]]
            for p in data:
                rows.append([
                    str(p.get('id','')), 
                    p.get('date',''), 
                    p.get('content',''),
                    json.dumps(p.get('images', [])), 
                    json.dumps(p.get('video', [])),
                    p.get('color', '#A370F7'), 
                    p.get('price', 0), 
                    0,
                    json.dumps(p.get('reactions', {})),
                    json.dumps(p.get('comments', []))
                ])
            ws.clear()
            ws.update(rows)
        except Exception as e:
            st.error(f"⚠️ บันทึก Sheets ไม่ได้ (แต่เซฟลงเครื่องแล้ว): {e}")
    
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

# --- PROFILE & MAILBOX (ย่อ) ---
def load_profile():
    sh = get_gsheet_client()
    if sh:
        try:
            records = sh.worksheet("profile").get_all_records()
            pf = {}
            for r in records:
                try: val = json.loads(r['value'])
                except: val = r['value']
                pf[r['key']] = val
            return pf
        except: pass
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_profile(data):
    sh = get_gsheet_client()
    if sh:
        try:
            rows = [["key", "value"]]
            for k,v in data.items():
                val = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                rows.append([k, val])
            sh.worksheet("profile").clear()
            sh.worksheet("profile").update(rows)
        except: pass
    with open(PROFILE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def load_mailbox():
    sh = get_gsheet_client()
    if sh:
        try: return sh.worksheet("mailbox").get_all_records()
        except: pass
    if os.path.exists(MAILBOX_FILE):
        with open(MAILBOX_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return []

def save_mailbox(data):
    sh = get_gsheet_client()
    if sh:
        try:
            rows = [["date", "text"]]
            for m in data: rows.append([m['date'], m['text']])
            sh.worksheet("mailbox").clear()
            sh.worksheet("mailbox").update(rows)
        except: pass
    with open(MAILBOX_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# --- INIT SESSION ---
if 'num_img_links' not in st.session_state: st.session_state['num_img_links'] = 1
if 'num_vid_links' not in st.session_state: st.session_state['num_vid_links'] = 1
if 'is_admin' not in st.session_state: st.session_state['is_admin'] = False
if 'user_reactions' not in st.session_state: st.session_state['user_reactions'] = {}
# Token Init
for k in ['feed_tokens','bar_tokens']: 
    if k not in st.session_state: st.session_state[k] = 5
for k in ['last_token_regen','last_bar_regen','last_comment_time','last_fortune_time','last_gossip_time','last_mailbox_time','last_choice_time','last_stock_trade']:
    if k not in st.session_state: st.session_state[k] = 0

# Regen Logic
now = time.time()
if now - st.session_state['last_token_regen'] >= 60:
    st.session_state['feed_tokens'] = min(5, st.session_state['feed_tokens'] + int((now - st.session_state['last_token_regen'])//60))
    st.session_state['last_token_regen'] = now
if now - st.session_state['last_bar_regen'] >= 3600:
    st.session_state['bar_tokens'] = min(5, st.session_state['bar_tokens'] + int((now - st.session_state['last_bar_regen'])//3600))
    st.session_state['last_bar_regen'] = now

# --- SIDEBAR ---
st.sidebar.title("🍸 เมนูหลัก")
with st.sidebar.expander("🧚‍♀️ ถาม-ตอบ กับไมล่า"):
    st.info("พูดคุยกับน้องไมล่าได้ที่นี่ (ระบบจำลอง)")

with st.sidebar.expander("🥤 Treat Me"):
    pf_stats = load_profile()
    if 'treats' not in pf_stats: pf_stats['treats'] = {}
    st.write(f"Tokens: {st.session_state['feed_tokens']}/5")
    if st.button("ปลาส้มทอด 🐟"): 
        if st.session_state['feed_tokens'] > 0:
            st.session_state['feed_tokens'] -= 1
            pf_stats['treats']['ปลาส้มทอด 🐟'] = pf_stats['treats'].get('ปลาส้มทอด 🐟', 0) + 1
            save_profile(pf_stats)
            st.toast("บอส: ขอบคุณครับ!", icon="🐟"); st.rerun()
        else: st.error("Token หมด!")

# --- LOGIN ---
if not st.session_state['is_admin']:
    with st.sidebar.expander("🔐 Login"):
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("Login"):
            if u == "dearluxion" and p == "1212312121mc":
                st.session_state['is_admin'] = True; st.rerun()
            else: st.error("Wrong!")
else:
    if st.sidebar.button("Logout"): st.session_state['is_admin'] = False; st.rerun()

# --- MAIN PAGE ---
profile = load_profile()
st.title(f"👋 {profile.get('name', 'Dearluxion')}")
if profile.get('billboard',{}).get('text'):
    st.info(f"📢 **ประกาศ:** {profile['billboard']['text']}")

# --- ADMIN POST ---
if st.session_state['is_admin']:
    tab1, tab2 = st.tabs(["📝 เขียนโพสต์", "⚙️ ตั้งค่า"])
    with tab1:
        desc = st.text_area("ข้อความ")
        
        # Images
        c1, c2 = st.columns([1,1])
        if c1.button("➕ รูป"): st.session_state['num_img_links'] += 1
        if c2.button("➖ รูป") and st.session_state['num_img_links'] > 1: st.session_state['num_img_links'] -= 1
        img_links = [st.text_input(f"Link รูป {i+1}", key=f"il{i}") for i in range(st.session_state['num_img_links'])]
        
        # Videos
        c3, c4 = st.columns([1,1])
        if c3.button("➕ คลิป"): st.session_state['num_vid_links'] += 1
        if c4.button("➖ คลิป") and st.session_state['num_vid_links'] > 1: st.session_state['num_vid_links'] -= 1
        vid_links = [st.text_input(f"Link คลิป {i+1}", key=f"vl{i}") for i in range(st.session_state['num_vid_links'])]
        
        if st.button("🚀 โพสต์"):
            final_imgs = [convert_drive_link(l) for l in img_links if l]
            final_vids = [convert_drive_video_link(l) for l in vid_links if l]
            
            # Check Errors
            if any("ERROR" in x for x in final_imgs + final_vids):
                st.error("ลิงก์ผิด! (ห้ามใช้ลิงก์ Folder)"); st.stop()
                
            new_post = {
                "id": str(int(time.time())),
                "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                "content": desc,
                "images": final_imgs, "video": final_vids,
                "color": "#A370F7", "price": 0,
                "reactions": {}, "comments": []
            }
            
            curr = load_data()
            curr.append(new_post)
            save_data(curr)
            st.success("โพสต์สำเร็จ! (ลง Sheets แล้ว)"); time.sleep(1); st.rerun()

    with tab2:
        n_name = st.text_input("ชื่อเว็บ", profile.get('name',''))
        n_bill = st.text_input("ประกาศ", profile.get('billboard',{}).get('text',''))
        if st.button("บันทึก"):
            profile.update({'name':n_name, 'billboard':{'text':n_bill}})
            save_profile(profile); st.rerun()

# --- FEED ---
posts = load_data()
if not posts: st.info("ยังไม่มีโพสต์ (หรือยังไม่ได้เชื่อมต่อ Sheets)")
else:
    for p in reversed(posts):
        with st.container():
            st.markdown(f"**{profile.get('name','Dearluxion')}** <small>{p['date']}</small>", unsafe_allow_html=True)
            
            if p.get('images'):
                cols = st.columns(min(3, len(p['images'])))
                for idx, img in enumerate(p['images']): cols[idx%3].image(img)
            
            if p.get('video'):
                for v in p['video']:
                    if "drive.google.com" in v:
                        st.markdown(f'<iframe src="{v}" width="100%" height="320" style="border:none; border-radius:10px;"></iframe>', unsafe_allow_html=True)
                    else: st.video(v)
            
            st.write(p['content'])
            
            # Delete Button
            if st.session_state['is_admin']:
                if st.button("🗑️ ลบโพสต์", key=f"d{p['id']}"):
                    save_data([x for x in posts if str(x['id']) != str(p['id'])])
                    st.rerun()
            
            st.markdown("---")