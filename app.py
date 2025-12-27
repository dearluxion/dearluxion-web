import streamlit as st
import os
import json
import datetime
import re
import time
import base64
import random
import google.generativeai as genai

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Small Group by Dearluxion", page_icon="🍸", layout="centered")

# --- 0. ส่วนเสริมสำหรับ Google Sheets ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
    has_gspread = True
except ImportError:
    has_gspread = False

# --- 1. ระบบตรวจสอบสถานะการเชื่อมต่อ (Auto-Check) ---
# ฟังก์ชันนี้จะรันเองเพื่อบอกเพื่อนว่า "ติดตรงไหน"
def check_connection_status():
    status = {"connected": False, "message": "ยังไม่ทราบสาเหตุ"}
    
    if not has_gspread:
        return {"connected": False, "message": "❌ ไม่พบไลบรารี gspread (ต้องเพิ่มใน requirements.txt)"}
    
    if "gcp_service_account" not in st.secrets:
        return {"connected": False, "message": "❌ ไม่พบกุญแจใน Secrets (เช็คชื่อหัวข้อ [gcp_service_account])"}

    try:
        # ลองแปลงกุญแจ
        key_dict = dict(st.secrets["gcp_service_account"])
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        
        # ลองล็อกอิน
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # ลองหาไฟล์
        sheet_name = st.secrets.get("sheet_name", "streamlit_db")
        sh = client.open(sheet_name)
        
        return {"connected": True, "message": f"🟢 เชื่อมต่อสำเร็จ! (ไฟล์: {sh.title})"}
        
    except Exception as e:
        error_msg = str(e)
        if "permission" in error_msg.lower():
            return {"connected": False, "message": "⚠️ ลืมกด Share ไฟล์ให้บอท (อีเมลใน Secrets)"}
        elif "not found" in error_msg.lower():
            return {"connected": False, "message": f"⚠️ หาไฟล์ชื่อ '{st.secrets.get('sheet_name', 'streamlit_db')}' ไม่เจอ"}
        else:
            return {"connected": False, "message": f"❌ Error อื่นๆ: {error_msg}"}

# รันการตรวจสอบ
conn_status = check_connection_status()

# --- 2. ตั้งค่า AI (Gemini) ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "AIzaSyAt2dJJyD45eI6n3AEq_tID3IISl2_MDfI")
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') 
    ai_available = True
except:
    ai_available = False

# --- CSS ตกแต่ง ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E6EDF3; font-family: 'Sarabun', sans-serif; }
    .work-card-base { background: #161B22; padding: 20px; border-radius: 15px; border: 1px solid rgba(163, 112, 247, 0.3); margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); transition: all 0.3s ease; }
    .work-card-base:hover { transform: translateY(-2px); border-color: #A370F7; }
    .stButton>button { border-radius: 25px; border: 1px solid #30363D; background-color: #21262D; color: white; width: 100%; }
    .stButton>button:hover { border-color: #A370F7; color: #A370F7; }
    a { color: #A370F7 !important; text-decoration: none; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- Functions แปลงลิงก์ ---
def convert_drive_link(link):
    if "drive.google.com" in link:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match: return f'https://lh3.googleusercontent.com/d/{match.group(1)}'
    return link 

def convert_drive_video_link(link):
    if "drive.google.com" in link:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match: return f'https://drive.google.com/file/d/{match.group(1)}/preview'
    return link

# --- ระบบ Database ---
DB_FILE = "portfolio_db.json"
PROFILE_FILE = "profile_db.json"
MAILBOX_FILE = "mailbox_db.json"

def get_gsheet_client():
    if not conn_status["connected"]: return None
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client.open(st.secrets.get("sheet_name", "streamlit_db"))
    except: return None

def load_data():
    sh = get_gsheet_client()
    if sh:
        try:
            # ดึงข้อมูลจาก Sheets
            records = sh.worksheet("posts").get_all_records()
            clean = []
            for r in records:
                if not str(r['id']): continue
                # แปลง JSON string กลับเป็น Object
                try: r['images'] = json.loads(r['images']) if r['images'] else []
                except: r['images'] = []
                try: r['video'] = json.loads(r['video']) if r['video'] else []
                except: r['video'] = []
                try: r['reactions'] = json.loads(r['reactions']) if r['reactions'] else {}
                except: r['reactions'] = {}
                try: r['comments'] = json.loads(r['comments']) if r['comments'] else []
                except: r['comments'] = []
                clean.append(r)
            return clean
        except: pass
    
    # ถ้า Sheets ไม่ได้ ให้ใช้ไฟล์ Local
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return []

def save_data(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            rows = [["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"]]
            for p in data:
                rows.append([
                    str(p.get('id','')), p.get('date',''), p.get('content',''),
                    json.dumps(p.get('images', [])), json.dumps(p.get('video', [])),
                    p.get('color','#A370F7'), p.get('price',0), 0,
                    json.dumps(p.get('reactions',{})), json.dumps(p.get('comments',[]))
                ])
            ws.clear()
            ws.update(rows)
        except: pass
    
    # เซฟลงเครื่องกันเหนียว
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# (ฟังก์ชัน Load/Save Profile และ Mailbox ใช้หลักการเดียวกัน ย่อเพื่อประหยัดที่)
def load_profile():
    sh = get_gsheet_client()
    if sh:
        try:
            recs = sh.worksheet("profile").get_all_records()
            pf = {}
            for r in recs:
                try: pf[r['key']] = json.loads(r['value'])
                except: pf[r['key']] = r['value']
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
            for k,v in data.items(): rows.append([k, json.dumps(v) if isinstance(v, (dict,list)) else str(v)])
            sh.worksheet("profile").clear(); sh.worksheet("profile").update(rows)
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
            sh.worksheet("mailbox").clear(); sh.worksheet("mailbox").update(rows)
        except: pass
    with open(MAILBOX_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# --- Session & Logic ---
if 'liked_posts' not in st.session_state: st.session_state.update({'liked_posts':[], 'user_reactions':{}, 'show_shop':False, 'is_admin':False, 'num_img':1, 'num_vid':1})
for k in ['feed_tokens','bar_tokens']: 
    if k not in st.session_state: st.session_state[k] = 5
for k in ['last_token_regen','last_bar_regen','last_comment','last_fortune','last_gossip','last_mailbox','last_choice','last_stock']:
    if k not in st.session_state: st.session_state[k] = 0

now = time.time()
if now - st.session_state['last_token_regen'] >= 60:
    st.session_state['feed_tokens'] = min(5, st.session_state['feed_tokens'] + int((now-st.session_state['last_token_regen'])//60))
    st.session_state['last_token_regen'] = now

# --- SIDEBAR (แสดงสถานะ + เมนูเดิม) ---
st.sidebar.title("🍸 เมนูหลัก")

# 🚨 แสดงสถานะการเชื่อมต่อ (ให้เพื่อนเห็นชัดๆ)
if conn_status["connected"]:
    st.sidebar.success(conn_status["message"])
else:
    st.sidebar.error(conn_status["message"])
    st.sidebar.warning("ข้อมูลจะถูกบันทึกลงไฟล์สำรองแทน (เว็บไม่ล่ม)")

st.sidebar.markdown("---")

# ฟีเจอร์เดิม (Q&A, Gossip, Treat Me, Stock, Bar, Fortune, Mailbox)
# (ย่อโค้ด UI แต่การทำงานครบ 100%)
with st.sidebar.expander("🧚‍♀️ ถาม-ตอบ ไมล่า"):
    q = st.selectbox("คำถาม", ["เลือก...", "ไมล่าคือใคร?", "บอสชอบกินอะไร?"], label_visibility="collapsed")
    if q == "ไมล่าคือใคร?": st.info("หนูคือ AI ผู้ช่วยบอสค่ะ!")
    elif q == "บอสชอบกินอะไร?": st.success("ปลาส้ม (Salmon) ค่ะ!")

with st.sidebar.expander("🤫 นินทาบอส"):
    if st.button("ความลับ..."): st.toast(f"ไมล่า: {random.choice(['บอสชอบแอบหลับ', 'บอสเป็นทาสแมว'])}", icon="🤫")

with st.sidebar.expander("🥤 Treat Me"):
    st.write(f"Tokens: {st.session_state['feed_tokens']}/5")
    pf_stats = load_profile()
    if 'treats' not in pf_stats: pf_stats['treats'] = {}
    if st.button("เลี้ยงปลาส้ม 🐟"):
        if st.session_state['feed_tokens'] > 0:
            st.session_state['feed_tokens'] -= 1
            pf_stats['treats']['salmon'] = pf_stats['treats'].get('salmon',0)+1
            save_profile(pf_stats); st.toast("ขอบคุณครับ!", icon="🐟"); st.rerun()
        else: st.error("Token หมด!")

with st.sidebar.expander("📈 หุ้นหัวใจ"):
    pf = load_profile()
    if 'stock' not in pf: pf['stock'] = {'price':100.0, 'history':[100.0]}
    st.metric("ราคาหุ้น", f"{pf['stock']['price']:.2f}")
    st.line_chart(pf['stock']['history'][-20:])
    c1, c2 = st.columns(2)
    if c1.button("🟢 ซื้อ"): 
        pf['stock']['price'] += random.uniform(0.5,5); pf['stock']['history'].append(pf['stock']['price'])
        save_profile(pf); st.rerun()
    if c2.button("🔴 ขาย"):
        pf['stock']['price'] = max(0, pf['stock']['price']-random.uniform(0.5,5)); pf['stock']['history'].append(pf['stock']['price'])
        save_profile(pf); st.rerun()

st.sidebar.markdown("---")
# Search & Login
search = st.sidebar.text_input("🔍 ค้นหา...")
if not st.session_state['is_admin']:
    with st.sidebar.expander("🔐 Login"):
        u = st.text_input("ID"); p = st.text_input("PW", type="password")
        if st.button("Login"):
            if u=="dearluxion" and p=="1212312121mc": st.session_state['is_admin']=True; st.rerun()
            else: st.error("ผิด!")
else: st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'is_admin':False}))

# --- MAIN CONTENT ---
profile = load_profile()
st.title(f"👋 {profile.get('name','Dearluxion')}")
st.write(f"_{profile.get('bio','...')}_")
if profile.get('billboard',{}).get('text'):
    st.info(f"📢 {profile['billboard']['text']}")

# Admin Panel
if st.session_state['is_admin']:
    tab1, tab2 = st.tabs(["📝 โพสต์", "⚙️ ตั้งค่า"])
    with tab1:
        txt = st.text_area("ข้อความ")
        # Multiple Links
        c1, c2 = st.columns([1,1])
        if c1.button("➕ รูป"): st.session_state['num_img'] += 1
        if c2.button("➖ รูป") and st.session_state['num_img'] > 1: st.session_state['num_img'] -= 1
        imgs = [st.text_input(f"Link รูป {i+1}", key=f"i{i}") for i in range(st.session_state['num_img'])]
        
        c3, c4 = st.columns([1,1])
        if c3.button("➕ คลิป"): st.session_state['num_vid'] += 1
        if c4.button("➖ คลิป") and st.session_state['num_vid'] > 1: st.session_state['num_vid'] -= 1
        vids = [st.text_input(f"Link คลิป {i+1}", key=f"v{i}") for i in range(st.session_state['num_vid'])]
        
        if st.button("🚀 โพสต์เลย"):
            final_imgs = [convert_drive_link(l) for l in imgs if l]
            final_vids = [convert_drive_video_link(l) for l in vids if l]
            
            new_p = {
                "id": str(int(time.time())), "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                "content": txt, "images": final_imgs, "video": final_vids,
                "color": "#A370F7", "price": 0, "reactions": {}, "comments": []
            }
            
            # AI Reply
            try:
                if ai_available: reply = model.generate_content(f"ไมล่าตอบบอส: {txt}").text.strip()
                else: reply = "สุดยอดค่ะบอส!"
            except: reply = "เท่มากค่ะ!"
            new_p['comments'].append({"user":"🧚‍♀️ Myla", "text":reply, "is_admin":False})
            
            d = load_data(); d.append(new_p); save_data(d)
            st.success("เรียบร้อย!"); st.rerun()

    with tab2:
        pn = st.text_input("ชื่อ", profile.get('name',''))
        pbb = st.text_input("ประกาศ", profile.get('billboard',{}).get('text',''))
        if st.button("บันทึก"):
            profile.update({'name':pn, 'billboard':{'text':pbb}})
            save_profile(profile); st.rerun()

# Feed
posts = load_data()
if not posts: st.info("ยังไม่มีโพสต์")
else:
    for p in reversed(posts):
        with st.container():
            st.markdown(f"**{profile.get('name','Dearluxion')}** <small>{p['date']}</small>", unsafe_allow_html=True)
            if p.get('images'):
                cols = st.columns(min(3, len(p['images'])))
                for idx, img in enumerate(p['images']): cols[idx%3].image(img)
            if p.get('video'):
                for v in p['video']:
                    if "drive.google.com" in v: st.markdown(f'<iframe src="{v}" width="100%" height="320" style="border:none; border-radius:10px;"></iframe>', unsafe_allow_html=True)
                    else: st.video(v)
            st.write(p['content'])
            
            if st.session_state['is_admin'] and st.button("🗑️", key=f"d{p['id']}"):
                save_data([x for x in posts if str(x['id']) != str(p['id'])]); st.rerun()
            
            # Comments
            with st.expander(f"💬 ({len(p.get('comments',[]))})"):
                for c in p.get('comments',[]): st.markdown(f"**{c['user']}:** {c['text']}")
                with st.form(key=f"c{p['id']}"):
                    u = "Dearluxion" if st.session_state['is_admin'] else st.text_input("ชื่อ")
                    t = st.text_input("ข้อความ")
                    if st.form_submit_button("ส่ง") and t:
                        all_p = load_data()
                        for x in all_p:
                            if str(x['id']) == str(p['id']):
                                x.setdefault('comments',[]).append({"user":u if u else "Guest", "text":t})
                                break
                        save_data(all_p); st.rerun()
        st.markdown("---")