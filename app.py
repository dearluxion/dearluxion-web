import streamlit as st
import os
import datetime
import re
import time
import random
import base64
import plotly.graph_objects as go

# --- [IMPORTED MODULES] ---
from styles import get_css 
from utils import convert_drive_link, convert_drive_video_link, make_clickable, send_post_to_discord, exchange_code_for_token, get_discord_user
import data_manager as dm
import sidebar_manager as sm
import ai_manager as ai
try:
    import crypto_engine as ce
    crypto_available = True
except ImportError:
    crypto_available = False 

# --- 0. ตั้งค่า API KEY (Multi-Key Support) ---
# ดึง Key ทั้งหมดจาก Secrets
keys_bundle = [
    st.secrets.get("gemini", {}).get("api_key_1", ""),
    st.secrets.get("gemini", {}).get("api_key_2", ""),
    st.secrets.get("gemini", {}).get("api_key_3", ""),
    st.secrets.get("gemini", {}).get("api_key_4", ""),
    st.secrets.get("gemini", {}).get("api_key_5", "")
]

# [UPDATE] ดึง Bot Token และ Boss ID เพื่อส่งให้ AI Manager
bot_token = st.secrets.get("discord_bot", {}).get("token", "")
BOSS_ID = "420947252849410055" # ID ของท่าน Dearluxion

# ส่ง keys, token, boss_id ไปให้ AI Manager
ai_available = ai.init_ai(keys_bundle, bot_token, BOSS_ID)

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="Small Group by Dearluxion", page_icon="🍸", layout="centered")
st.markdown(get_css(), unsafe_allow_html=True)

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
if 'feed_tokens' not in st.session_state: st.session_state['feed_tokens'] = 5
if 'last_token_regen' not in st.session_state: st.session_state['last_token_regen'] = time.time()
if 'feed_msg' not in st.session_state: st.session_state['feed_msg'] = None
if 'bar_tokens' not in st.session_state: st.session_state['bar_tokens'] = 5
if 'last_bar_regen' not in st.session_state: st.session_state['last_bar_regen'] = time.time()
if 'bar_result' not in st.session_state: st.session_state['bar_result'] = None
if 'num_img_links' not in st.session_state: st.session_state['num_img_links'] = 1
if 'num_vid_links' not in st.session_state: st.session_state['num_vid_links'] = 1
if 'discord_user' not in st.session_state: st.session_state['discord_user'] = None
if 'show_crypto' not in st.session_state: st.session_state['show_crypto'] = False
if 'trigger_analysis' not in st.session_state: st.session_state['trigger_analysis'] = False
if 'show_code_zone' not in st.session_state: st.session_state['show_code_zone'] = False
if 'filtered' not in st.session_state: st.session_state['filtered'] = []
filtered = []  # ประกาศตัวแปร global ดักไว้เลย กันพลาด

# --- Login Discord Logic (Auto Admin Check) ---
if "code" in st.query_params:
    code = st.query_params["code"]
    try:
        # ดึงค่าจาก Secrets
        c_id = st.secrets["discord_oauth"]["client_id"]
        c_secret = st.secrets["discord_oauth"]["client_secret"]
        c_uri = st.secrets["discord_oauth"]["redirect_uri"]
        
        token_data = exchange_code_for_token(c_id, c_secret, code, c_uri)
        user_info = get_discord_user(token_data["access_token"])
        
        st.session_state['discord_user'] = user_info
        
        # --- 🚀 ส่วนเช็ค ID บอส (Hardcode ตามคำขอ) ---
        
        if str(user_info['id']) == BOSS_ID:
            st.session_state['is_admin'] = True
            st.toast(f"👑 ยินดีต้อนรับ Boss {user_info['username']}!", icon="😎")
        else:
            # ถ้าไม่ใช่บอส ให้เป็น User ธรรมดา
            st.session_state['is_admin'] = False 
            st.toast(f"สวัสดีคุณ {user_info['username']}!", icon="👋")
            
        st.query_params.clear() # ลบ code ออกจาก url
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Login ผิดพลาด: {e}")

# --- Token Regen Logic ---
now = time.time()
if now - st.session_state['last_token_regen'] >= 60: 
    st.session_state['feed_tokens'] = min(5, st.session_state['feed_tokens'] + int((now - st.session_state['last_token_regen']) // 60))
    st.session_state['last_token_regen'] = now

if now - st.session_state['last_bar_regen'] >= 3600:
    st.session_state['bar_tokens'] = min(5, st.session_state['bar_tokens'] + int((now - st.session_state['last_bar_regen']) // 3600))
    st.session_state['last_bar_regen'] = now

# --- 2. Render Sidebar ---
# ไม่ต้องส่ง model แล้ว ส่งแค่สถานะว่าพร้อมไหม
search_query, selected_zone = sm.render_sidebar(ai_available) 

# --- 3. Header & Profile ---
profile_data = dm.load_profile()
user_emoji = profile_data.get('emoji', '😎') 
user_status = profile_data.get('status', 'ยินดีต้อนรับสู่โลกของdearluxion ✨')

if not st.session_state['is_admin']:
    hour = datetime.datetime.now().hour
    greeting = "สวัสดีตอนเช้าค่ะ" if 5 <= hour < 12 else "สวัสดีตอนบ่ายค่ะ" if 12 <= hour < 18 else "สวัสดีตอนค่ำค่ะ"
    st.info(f"🧚‍♀️ **ไมล่า:** {greeting} พี่จ๋า~ กดลูกศร **มุมซ้ายบน** ↖️ เพื่อเปิดเมนูคุยกับไมล่าได้นะคะ!")

top_col1, top_col2 = st.columns([8, 1])
with top_col1:
    col_p1, col_p2 = st.columns([1.5, 6])
    with col_p1:
        st.markdown(f"""
            <div style="font-size: 60px; line-height: 1; filter: drop-shadow(0 0 10px #A370F7); text-align: center; cursor:default;">
                {user_emoji}
            </div>
        """, unsafe_allow_html=True)
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

# [Boss's Billboard]
if profile_data.get('billboard'):
    bb = profile_data['billboard']
    if bb.get('text'):
        st.markdown(f"""
        <div class="boss-billboard">
            <div class="billboard-icon">📢 ประกาศจากบอส</div>
            <div class="billboard-text">{bb['text']}</div>
            <div class="billboard-time">🕒 อัปเดตล่าสุด: {bb['timestamp']}</div>
        </div>
        """, unsafe_allow_html=True)

# --- 4. Admin Panel ---
if st.session_state['is_admin']:
    tab_post, tab_profile, tab_inbox, tab_code = st.tabs(["📝 เขียน / ขายของ", "👤 แก้ไขโปรไฟล์", "📬 อ่านจดหมายลับ", "💻 ลงโค้ด"])
    
    with tab_post:
        st.info("ℹ️ **แจ้งเตือนจาก Eri:** ระบบอัปโหลดไฟล์ถูกปิดแล้วนะ ใช้ลิงก์ Google Drive หรือลิงก์เว็บแทนนะ เว็บจะได้ไม่หน่วง")
        col1, col2 = st.columns([3, 1])
        with col1:
            new_desc = st.text_area("เนื้อหา (Story)", height=150)
        with col2:
            st.markdown("##### 📷 รูปภาพ (Link Only)")
            img_links = []
            c_plus, c_minus = st.columns([1,1])
            with c_plus:
                if st.button("➕ เพิ่มช่องรูป", key="add_img_field"): st.session_state['num_img_links'] += 1
            with c_minus:
                if st.button("➖ ลบช่องรูป", key="del_img_field"):
                    if st.session_state['num_img_links'] > 1: st.session_state['num_img_links'] -= 1
            for i in range(st.session_state['num_img_links']):
                val = st.text_input(f"ลิงก์รูป {i+1}", key=f"img_lnk_{i}", placeholder="Google Drive / Web Link")
                if val: img_links.append(val)
            
            st.markdown("##### 🎥 วิดีโอ (Link Only)")
            vid_links = []
            v_plus, v_minus = st.columns([1,1])
            with v_plus:
                if st.button("➕ เพิ่มช่องคลิป", key="add_vid_field"): st.session_state['num_vid_links'] += 1
            with v_minus:
                if st.button("➖ ลบช่องคลิป", key="del_vid_field"):
                    if st.session_state['num_vid_links'] > 1: st.session_state['num_vid_links'] -= 1
            for i in range(st.session_state['num_vid_links']):
                val = st.text_input(f"ลิงก์คลิป {i+1}", key=f"vid_lnk_{i}", placeholder="Google Drive / Web Link")
                if val: vid_links.append(val)
            
            post_color = st.color_picker("สีธีม", "#A370F7")
            price = st.number_input("💰 ราคา (ใส่ 0 = ไม่ขาย)", min_value=0, value=0)

            # [NEW] Checkbox ควบคุมการส่ง Webhook
            st.markdown("---")
            send_webhook = st.checkbox("📢 ส่งแจ้งเตือนเข้า Discord", value=True, help="ติ๊กออกถ้าจะโพสต์เงียบๆ เพื่อทดสอบเว็บ")

        if st.button("🚀 โพสต์เลย", use_container_width=True):
            # --- 1. แปลงลิงก์รูปและวิดีโอ ---
            link_errors = []
            final_img_links = []
            final_vid_links = []
            
            for lnk in img_links:
                conv = convert_drive_link(lnk.strip())
                if conv.startswith("ERROR:"): link_errors.append(f"รูป: {conv}")
                else: final_img_links.append(conv)
            
            for lnk in vid_links:
                conv = convert_drive_video_link(lnk.strip())
                if conv.startswith("ERROR:"): link_errors.append(f"วิดีโอ: {conv}")
                else: final_vid_links.append(conv)

            if link_errors:
                for err in link_errors: st.error(err)
            elif new_desc:
                # --- 2. เตรียมโครงสร้างโพสต์ ---
                new_post = {
                    "id": str(datetime.datetime.now().timestamp()),
                    "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "content": new_desc,
                    "images": final_img_links,
                    "video": final_vid_links,
                    "color": post_color,
                    "price": price,
                    "likes": 0, # เดี๋ยวให้ AI มาบวกเพิ่ม
                    "reactions": {'😻': 0, '🙀': 0, '😿': 0, '😾': 0, '🧠': 0},
                    "comments": []
                }
                
                # --- 3. เรียกกองทัพ AI (Myla, Ariel และหน้าม้า) ---
                # NEW LOGIC: ดึงรูปภาพแรกไปให้ AI ดูด้วย!
                main_img_url = None
                if final_img_links:
                    main_img_url = final_img_links[0]
                
                # [UPDATE] หาลิงก์ YouTube อันแรกจากโพสต์ (ถ้ามี)
                main_yt_url = None
                for v in vid_links: # เช็คจากลิงก์ดิบที่ user ใส่เข้ามา
                    if "youtu" in v:
                        main_yt_url = v
                        break

                with st.spinner("📦 กำลังเรียกหน้าม้า AI (กำลังดูคลิปและส่องรูป)..."):
                    # ส่งทั้ง Text, รูป และ YouTube URL ไปให้ AI
                    ai_engagements = ai.generate_post_engagement(new_desc, main_img_url, main_yt_url)
                
                # --- 4. วนลูปใส่ข้อมูลที่ AI ตอบกลับมา ---
                for engagement in ai_engagements:
                    # ใส่คอมเมนต์
                    new_post['comments'].append({
                        "user": engagement.get('user', 'Anonymous'),
                        "text": engagement.get('text', '...'),
                        "is_admin": False,
                        "image": None
                    })
                    
                    # กด Reaction (ถ้า AI เลือกกด)
                    react_emoji = engagement.get('reaction')
                    valid_emojis = ['😻', '🙀', '😿', '😾', '🧠']
                    
                    if react_emoji and react_emoji in valid_emojis:
                        # บวกยอด Reaction
                        new_post['reactions'][react_emoji] += 1
                        
                        # ถือว่ากด Heart คือกด Like ด้วย (Optional)
                        if react_emoji == '😻': 
                            new_post['likes'] += 1

                # --- 5. บันทึกลง Database ---
                current = dm.load_data()
                current.append(new_post)
                dm.save_data(current)
                
                # [NEW] Logic การส่ง Webhook ตาม Checkbox
                if send_webhook:
                    try:
                        send_post_to_discord(new_post)
                        st.toast("ส่งเข้า Discord เรียบร้อย!", icon="📢")
                    except: pass
                else:
                    st.toast("บันทึกโพสต์แล้ว (ไม่ได้ส่งเข้า Discord)", icon="🤫")

                # สรุปผล
                st.success(f"เรียบร้อย! มีคนมาเม้นตั้ง {len(ai_engagements)} คนแน่ะ (Myla & Ariel มาครบ!)")
                st.session_state['num_img_links'] = 1
                st.session_state['num_vid_links'] = 1
                time.sleep(2); st.rerun()
            else: st.warning("พิมพ์อะไรหน่อยสิครับ")

    with tab_profile:
        st.markdown("### 📢 จัดการป้ายไฟ")
        bb_text = st.text_input("ข้อความบนป้ายไฟ", value=profile_data.get('billboard', {}).get('text', ''))
        c_bb1, c_bb2 = st.columns(2)
        with c_bb1:
            if st.button("บันทึกป้ายไฟ"):
                profile_data['billboard'] = {'text': bb_text, 'timestamp': datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}
                dm.save_profile(profile_data)
                st.success("อัปเดตป้ายไฟแล้ว!")
                st.rerun()
        with c_bb2:
            if st.button("ลบป้ายไฟ", type="primary"):
                profile_data['billboard'] = {'text': '', 'timestamp': ''}
                dm.save_profile(profile_data)
                st.rerun()
        
        st.markdown("---")
        st.markdown("### ⚙️ ตั้งค่าระบบ AI & ฟีเจอร์")
        current_settings = profile_data.get('settings', {})
        enable_bar = st.checkbox("เปิดบาร์เทนเดอร์ (Mood Mocktail)", value=current_settings.get('enable_bar', True))
        enable_ariel = st.checkbox("เปิดแชท Ariel (คุยกับเอเรียล)", value=current_settings.get('enable_ariel', True))
        enable_battle = st.checkbox("เปิดสังเวียน (Myla vs Ariel)", value=current_settings.get('enable_battle', True))

        if st.button("บันทึกการตั้งค่า"):
            if 'settings' not in profile_data: profile_data['settings'] = {}
            profile_data['settings']['enable_bar'] = enable_bar
            profile_data['settings']['enable_ariel'] = enable_ariel
            profile_data['settings']['enable_battle'] = enable_battle
            dm.save_profile(profile_data) 
            st.success("บันทึกการตั้งค่าแล้ว!")
            time.sleep(1); st.rerun()

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
                profile_data.update({"name": p_name, "emoji": p_emoji, "status": p_status, "bio": p_bio, "discord": p_discord, "ig": p_ig, "extras": p_ex})
                dm.save_profile(profile_data)
                st.success("อัปเดตแล้ว!")
                st.rerun()

        st.markdown("---")
        if st.button("⚠️ กดเพื่อส่งทุกโพสต์ (ตั้งแต่แรก) ไป Discord"):
            all_posts = dm.load_data()
            my_bar = st.progress(0)
            status_text = st.empty()
            total = len(all_posts)
            for i, p in enumerate(all_posts):
                status_text.text(f"กำลังส่งโพสต์วันที่ {p['date']} ({i+1}/{total})...")
                send_post_to_discord(p)
                time.sleep(2)
                my_bar.progress((i + 1) / total)
            status_text.success("✅ ส่งครบทุกโพสต์แล้วครับบอส!")
            
    with tab_inbox:
        st.markdown("### 💌 จดหมายลับจากแฟนคลับ")
        msgs = dm.load_mailbox()
        if msgs:
            if st.button("ลบจดหมายทั้งหมด"):
                if os.path.exists(dm.MAILBOX_FILE): os.remove(dm.MAILBOX_FILE)
                st.rerun()
            for m in reversed(msgs):
                st.info(f"📅 **{m['date']}**: {m['text']}")
        else: st.info("ยังไม่มีจดหมายลับมาส่งครับ")
    st.markdown("---")
    
    with tab_code:
        st.markdown("### 💻 เพิ่ม Code Snippet ใหม่")
        with st.form("add_snippet_form"):
            s_title = st.text_input("ชื่อโปรเจกต์/Snippets:", placeholder="เช่น Discord Bot Template")
            s_lang = st.selectbox("ภาษา:", ["python", "javascript", "html", "css", "sql"])
            s_desc = st.text_area("คำอธิบายสั้นๆ:", placeholder="โค้ดนี้ใช้สำหรับ...")
            s_code = st.text_area("วาง Source Code ที่นี่:", height=200)
            s_qr = st.text_input("ลิงก์รูป QR Code (PromptPay):", placeholder="URL รูป QR Code ของบอส (Google Drive/Web)")
            if st.form_submit_button("💾 บันทึก Code"):
                if s_title and s_code:
                    snippets = dm.load_snippets()
                    new_snippet = {
                        "id": str(int(time.time())),
                        "title": s_title,
                        "lang": s_lang,
                        "desc": s_desc,
                        "code": s_code,
                        "qr_link": convert_drive_link(s_qr) if s_qr else ""
                    }
                    snippets.append(new_snippet)
                    dm.save_snippets(snippets)
                    st.success("ลงโค้ดเรียบร้อย! เตรียมรับค่ากาแฟ ☕")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("ใส่ชื่อกับโค้ดก่อนสิครับบอส!")
        st.markdown("---")
        st.markdown("### 🗑️ ลบ Snippet")
        snippets = dm.load_snippets()
        if snippets:
            for idx, s in enumerate(snippets):
                c1, c2 = st.columns([4, 1])
                with c1: st.markdown(f"**{idx+1}. {s['title']}** ({s['lang']})")
                with c2:
                    if st.button("ลบ", key=f"del_snip_{idx}"):
                        snippets.pop(idx)
                        dm.save_snippets(snippets)
                        st.rerun()
        else:
            st.info("ยังไม่มี Snippet ครับ")

# --- 5. Feed Display ---
# [Crypto War Room Display (RESTORED THAI VERSION)]
if st.session_state.get('show_crypto', False):
    filtered = []  # รีเซต filtered สำหรับโหมด Crypto
    if not crypto_available:
        st.error("⚠️ โมดูล crypto_engine ยังไม่พร้อม กรุณาติดตั้ง")
    else:
        st.markdown("## 📈 Crypto War Room (Shadow Oracle)")
        st.caption("พื้นที่วิเคราะห์กราฟด้วย AI ระดับ God-Tier สำหรับท่าน Dearluxion (หน่วย: THB)")
        
        # รายชื่อเหรียญครบ 8 ตัว
        coin_list = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "PEPE", "SHIB"]
        
        col_c1, col_c2 = st.columns([2, 1])
        with col_c1:
            coin_select = st.selectbox("เลือกสินทรัพย์ประหาร:", coin_list)
        with col_c2:
            if st.button("วิเคราะห์เหรียญนี้", type="primary", use_container_width=True):
                st.session_state['trigger_analysis'] = True
                st.session_state['analyze_all'] = False # Reset โหมดเหมา
        
        # ปุ่มวิเคราะห์เหมาเข่ง
        if st.button("🚀 วิเคราะห์ทั้ง 8 เหรียญ โปรดของท่านเดียร์", use_container_width=True):
            st.session_state['analyze_all'] = True
            st.session_state['trigger_analysis'] = False
            st.rerun()

        # Helper แปลผล Fear Greed (แปลไทย)
        def translate_fng(classification):
            mapping = {
                "Extreme Fear": "กลัวสุดขีด (Extreme Fear)",
                "Fear": "กลัว (Fear)",
                "Neutral": "เฉยๆ (Neutral)",
                "Greed": "โลภ (Greed)",
                "Extreme Greed": "โลภสุดขีด (Extreme Greed)"
            }
            return mapping.get(classification, classification)

        # =========================================================
        # CASE A: วิเคราะห์ทีละเหรียญ (THAI VERSION)
        # =========================================================
        if not st.session_state.get('analyze_all'):
            # ดึงข้อมูล
            with st.spinner(f"กำลังดึงข้อมูลตลาดล่าสังหารของ {coin_select}..."):
                # crypto_engine จะ map เป็น THB ให้อัตโนมัติในไฟล์ ce.py ที่แก้ไป
                df = ce.get_crypto_data(coin_select)
                news = ce.get_crypto_news(coin_select)
                fg_index = ce.get_fear_and_greed()
            
            if df is not None:
                # 1. แสดงกราฟ Interactive
                latest_price = df['Close'].iloc[-1]
                price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2] if len(df) > 1 else 0
                color_price = "green" if price_change >= 0 else "red"
                
                # Format ราคา THB
                price_fmt = "{:,.4f}" if coin_select in ["SHIB", "PEPE", "DOGE"] else "{:,.2f}"
                st.markdown(f"### 💎 {coin_select} ราคาล่าสุด: <span style='color:{color_price}'>฿{price_fmt.format(latest_price)}</span>", unsafe_allow_html=True)
                
                # สร้างกราฟด้วย Plotly (แปล Label ไทย)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'], name='ราคา'))
                if 'EMA_50' in df.columns:
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1), name='เส้นค่าเฉลี่ย 50'))
                if 'EMA_200' in df.columns:
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], line=dict(color='blue', width=1), name='เส้นค่าเฉลี่ย 200'))
                
                fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                # 2. Dashboard Indicators (แปลไทย)
                k1, k2, k3, k4 = st.columns(4)
                rsi_val = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50
                macd_val = df['MACD'].iloc[-1] if 'MACD' in df.columns else 0
                macd_signal = df['MACD_SIGNAL'].iloc[-1] if 'MACD_SIGNAL' in df.columns else 0
                
                rsi_status = "ซื้อมากเกิน (Overbought)" if rsi_val > 70 else "ขายมากเกิน (Oversold)" if rsi_val < 30 else "ปกติ (Neutral)"
                k1.metric("RSI (14)", f"{rsi_val:.2f}", delta=rsi_status)
                
                k2.metric("MACD", f"{macd_val:.6f}")
                
                fg_val = fg_index.get('value', 'N/A')
                fg_class = translate_fng(fg_index.get('value_classification', ''))
                k3.metric("ดัชนีกลัว/โลภ", f"{fg_val}", fg_class)
                
                ema_trend = "N/A"
                if 'EMA_200' in df.columns:
                    try:
                        c_val = float(df['Close'].iloc[-1])
                        e_val = float(df['EMA_200'].iloc[-1])
                        ema_trend = "ขาขึ้น (Bullish)" if c_val > e_val else "ขาลง (Bearish)"
                    except: pass
                
                k4.metric("แนวโน้ม EMA", ema_trend)

                # 3. AI Analysis Section (MODIFIED - WITH CACHE CHECK)
                st.markdown("---")
                if st.session_state.get('trigger_analysis'):
                    st.markdown(f"### 🧠 ข้อมูลจากนักวิเคราะห์ (AI) - {coin_select}")
                    
                    with st.chat_message("ai", avatar="👁️"):
                        # 1. เช็ค Cache ก่อน
                        cached_data = dm.get_crypto_cache(coin_select)
                        
                        if cached_data:
                            # เจอข้อมูลของวันนี้ -> แสดงเลย ไม่ต้องโหลด
                            st.success(f"⚡ โหลดข้อมูลวิเคราะห์ประจำวันสำเร็จ (อัปเดตเมื่อ: {cached_data['updated_at']} น.)")
                            st.markdown(cached_data['analysis'])
                            st.caption("ℹ️ ข้อมูลนี้ถูกวิเคราะห์ไว้แล้ววันนี้เพื่อประหยัดทรัพยากร (Cache Hit)")
                            st.session_state['trigger_analysis'] = False # ปิด Trigger
                            
                        else:
                            # ไม่เจอข้อมูล (หรือเป็นวันใหม่) -> เรียก AI
                            msg_loading = f"กำลังเชื่อมต่อจิตกับ Gemini 2.5 เพื่อวิเคราะห์ {coin_select} (THB)..."
                            with st.spinner(msg_loading):
                                # [UPDATED V2] ส่งข้อมูล Indicators ใหม่ๆทั้งหมด + Pivot Points, StochRSI, OBV
                                indicators = {
                                    "rsi": f"{rsi_val:.2f}",
                                    "stoch_k": f"{df['Stoch_K'].iloc[-1]:.2f}" if 'Stoch_K' in df.columns else "50",  # NEW V2
                                    "macd": f"{macd_val:.6f}",
                                    "macd_signal": f"{macd_signal:.6f}",
                                    "adx": f"{df['ADX'].iloc[-1]:.2f}" if 'ADX' in df.columns else "20",
                                    "atr": f"{df['ATR'].iloc[-1]:,.2f}" if 'ATR' in df.columns else "0",
                                    "obv_slope": "เงินไหลเข้า (Positive)" if df['OBV_Slope'].iloc[-1] > 0 else "เงินไหลออก (Negative)" if 'OBV_Slope' in df.columns and df['OBV_Slope'].iloc[-1] < 0 else "N/A",  # NEW V2
                                    "pivot_p": f"{df['Pivot_P'].iloc[-1]:.2f}" if 'Pivot_P' in df.columns else f"{latest_price:.2f}",  # NEW V2
                                    "pivot_s1": f"{df['Pivot_S1'].iloc[-1]:.2f}" if 'Pivot_S1' in df.columns else f"{latest_price * 0.95:.2f}",  # NEW V2
                                    "pivot_r1": f"{df['Pivot_R1'].iloc[-1]:.2f}" if 'Pivot_R1' in df.columns else f"{latest_price * 1.05:.2f}",  # NEW V2
                                    "support": f"{df['Support_Level'].iloc[-1]:,.2f}" if 'Support_Level' in df.columns else f"{latest_price * 0.95:,.2f}",
                                    "resistance": f"{df['Resistance_Level'].iloc[-1]:,.2f}" if 'Resistance_Level' in df.columns else f"{latest_price * 1.05:,.2f}"
                                }
                                
                                if ai_available and crypto_available:
                                    # เรียก AI ด้วยข้อมูล Quant ใหม่ (V2 God Mode)
                                    analysis_result = ai.analyze_crypto_god_mode(coin_select, latest_price, indicators, news, fg_index)
                                    
                                    # บันทึกลง Cache ทันที
                                    dm.update_crypto_cache(coin_select, analysis_result)
                                    
                                    st.markdown(analysis_result)
                                    st.caption(f"✨ วิเคราะห์สดเสร็จสิ้น (บันทึกเวลา: {datetime.datetime.now().strftime('%H:%M')} น.)")
                                else:
                                    st.error("ไม่สามารถทำการวิเคราะห์ได้ เนื่องจาก API ยังไม่พร้อม")
                                
                                st.session_state['trigger_analysis'] = False 
                else:
                    st.info("กดปุ่ม 'เรียกดูข้อมูล (God Mode)' ด้านบนเพื่อดูคำทำนาย")
            else:
                st.error("ไม่สามารถดึงข้อมูลกราฟได้ (ตรวจสอบคู่เหรียญ THB)")

        # =========================================================
        # CASE B: วิเคราะห์รวดเดียว 8 เหรียญ (God Mode Batch - THAI)
        # =========================================================
        else:
            st.markdown("### 🚀 รายงานสรุป 8 เหรียญโปรด (God Mode Batch)")
            if st.button("❌ ปิดโหมดวิเคราะห์รวม"):
                st.session_state['analyze_all'] = False
                st.rerun()

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # วนลูปวิเคราะห์ทีละตัว
            for idx, c_symbol in enumerate(coin_list):
                status_text.text(f"กำลังเจาะระบบวิเคราะห์ {c_symbol} ({idx+1}/{len(coin_list)})...")
                
                # 1. เช็คก่อนว่าวันนี้วิเคราะห์ไปหรือยัง (ประหยัด API บอส)
                cached_data = dm.get_crypto_cache(c_symbol)
                
                if cached_data:
                    # ถ้ามีใน Cache แล้ว ให้ดึงมาโชว์เลย
                    with st.expander(f"💎 {c_symbol} (จากฐานข้อมูลเดิมวันนี้)", expanded=False):
                        st.success(f"⚡ ใช้ข้อมูลเดิม (อัปเดตเมื่อ: {cached_data['updated_at']} น.)")
                        st.markdown(cached_data['analysis'])
                else:
                    # 2. ถ้ายังไม่มี ให้ดึงข้อมูลกราฟและสั่ง AI วิเคราะห์ใหม่
                    df_batch = ce.get_crypto_data(c_symbol)
                    
                    if df_batch is not None:
                        last_p = df_batch['Close'].iloc[-1]
                        rsi_v = df_batch['RSI'].iloc[-1] if 'RSI' in df_batch.columns else 50
                        
                        with st.expander(f"💎 {c_symbol} : ฿{last_p:,.4f} | RSI: {rsi_v:.1f}", expanded=False):
                            if ai_available:
                                # เตรียมอินดิเคเตอร์ (V2 - รวมทั้ง Pivot, Stoch, OBV)
                                indicators_b = {
                                    "rsi": f"{rsi_v:.2f}",
                                    "stoch_k": f"{df_batch['Stoch_K'].iloc[-1]:.2f}" if 'Stoch_K' in df_batch.columns else "50",  # NEW V2
                                    "macd": f"{df_batch['MACD'].iloc[-1]:.6f}" if 'MACD' in df_batch.columns else "0",
                                    "macd_signal": f"{df_batch['MACD_SIGNAL'].iloc[-1]:.6f}" if 'MACD_SIGNAL' in df_batch.columns else "0",
                                    "adx": f"{df_batch['ADX'].iloc[-1]:.2f}" if 'ADX' in df_batch.columns else "20",
                                    "atr": f"{df_batch['ATR'].iloc[-1]:.2f}" if 'ATR' in df_batch.columns else "0",
                                    "obv_slope": "เงินไหลเข้า (Positive)" if df_batch['OBV_Slope'].iloc[-1] > 0 else "เงินไหลออก (Negative)" if 'OBV_Slope' in df_batch.columns and df_batch['OBV_Slope'].iloc[-1] < 0 else "N/A",  # NEW V2
                                    "pivot_p": f"{df_batch['Pivot_P'].iloc[-1]:.2f}" if 'Pivot_P' in df_batch.columns else f"{last_p:.2f}",  # NEW V2
                                    "pivot_s1": f"{df_batch['Pivot_S1'].iloc[-1]:.2f}" if 'Pivot_S1' in df_batch.columns else f"{last_p * 0.95:.2f}",  # NEW V2
                                    "pivot_r1": f"{df_batch['Pivot_R1'].iloc[-1]:.2f}" if 'Pivot_R1' in df_batch.columns else f"{last_p * 1.05:.2f}",  # NEW V2
                                    "support": f"{df_batch['Support_Level'].iloc[-1]:.2f}" if 'Support_Level' in df_batch.columns else f"{last_p * 0.95:.2f}",
                                    "resistance": f"{df_batch['Resistance_Level'].iloc[-1]:.2f}" if 'Resistance_Level' in df_batch.columns else f"{last_p * 1.05:.2f}"
                                }
                                
                                # สั่ง AI วิเคราะห์สด (God Mode V2)
                                res_batch = ai.analyze_crypto_god_mode(c_symbol, last_p, indicators_b, "วิเคราะห์ตามกราฟเทคนิคอลล่าสุด", {"value":"50", "value_classification":"Neutral"})
                                st.markdown(res_batch)
                                
                                # --- [จุดที่เพิ่ม] บันทึกลง Google Sheets ทันที ---
                                dm.update_crypto_cache(c_symbol, res_batch)
                                st.caption(f"✅ บันทึกลงระบบสำเร็จเมื่อ {datetime.datetime.now().strftime('%H:%M')} น.")
                            else:
                                st.error("AI ไม่พร้อมใช้งาน")
                
                progress_bar.progress((idx + 1) / len(coin_list))
                time.sleep(0.5) 
            
            status_text.success("✅ วิเคราะห์และบันทึกข้อมูลครบทั้ง 8 เหรียญแล้วครับท่านเดียร์!")

elif st.session_state.get('show_code_zone', False):
    st.markdown("## 💻 Code Showcase & Portfolio")
    st.caption(f"คลังแสงโค้ดของ {profile_data.get('name', 'Dearluxion')} | ก๊อปไปใช้ได้เลย (ถ้าใจดีเลี้ยงกาแฟผมได้นะ ☕)")
    
    with st.expander("ℹ️ อ่านก่อนนำไปใช้ (License)", expanded=False):
        st.info("Code ทั้งหมดในนี้แจกฟรีเพื่อการศึกษาครับ! สามารถนำไปพัฒนาต่อได้เลย แต่ถ้านำไปใช้เชิงพาณิชย์ รบกวนเลี้ยงกาแฟสักแก้วจะเป็นกำลังใจมากครับ 💖")
    
    snippets = dm.load_snippets()
    
    if not snippets:
        st.info("🚧 กำลังรวบรวมโค้ดเทพๆ มาลงครับ... (รอแป๊บ)")
    else:
        for s in reversed(snippets):
            st.markdown(f"""
            <div style="background:#161B22; padding:20px; border-radius:15px; border:1px solid #30363D; margin-bottom:20px; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h3 style="color:#A370F7; margin:0;">{s['title']}</h3>
                    <span style="background:#21262D; padding:2px 10px; border-radius:10px; font-size:12px; color:#8B949E;">{s['lang'].upper()}</span>
                </div>
                <p style="color:#E6EDF3; font-size:14px; margin-top:10px;">{s['desc']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.code(s['code'], language=s['lang'])
            
            c_donate, c_copy = st.columns([1, 3])
            with c_donate:
                if st.button(f"☕ เลี้ยงกาแฟ ({s['title']})", key=f"donate_{s['id']}", type="primary"):
                    st.toast("ขอบคุณที่สนับสนุนครับ! 🙏", icon="💖")
                    with st.expander("📸 สแกน QR Code เพื่อเลี้ยงกาแฟ", expanded=True):
                        if s.get('qr_link'):
                            st.image(s['qr_link'], caption="PromptPay: Chotiwut Maneekong", width=250)
                            st.success("โอนแล้วส่งสลิปมาอวดใน Discord ได้นะครับ!")
                        else:
                            st.warning("บอสยังไม่ได้แปะ QR Code ครับ (โอนทิพย์ไปก่อนนะ 😅)")
            
            st.markdown("---")
    
    filtered = []  # รีเซต filtered สำหรับโหมด Code Zone

elif st.session_state['show_shop']:
    st.markdown("## 🛒 ร้านค้า (Shop Zone)")
    with st.expander("🧚‍♀️ พี่จ๋า~ หาทางกลับไม่เจอเหรอคะ? (จิ้มไมล่าสิ!) 💖", expanded=True):
        st.markdown("""<div class="cute-guide">✨ ทางลัดพิเศษสำหรับพี่คนโปรดของไมล่า! 🌈</div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 กลับบ้านกับไมล่า!", use_container_width=True):
                st.session_state['show_shop'] = False
                st.balloons(); time.sleep(1); st.rerun()
        with c2: st.info("👈 กดปุ่มนี้ ไมล่าจะพาพี่กลับหน้าหลักเองค่ะ!")
    posts = dm.load_data()
    filtered = [p for p in posts if p.get('price', 0) > 0 or "#ร้านค้า" in p['content']]
    if not filtered: st.warning("ยังไม่มีสินค้าวางขายจ้า")
else:
    posts = dm.load_data()
    filtered = posts

if filtered:
    for post in reversed(filtered):
        accent = post.get('color', '#A370F7')
        if 'reactions' not in post: post['reactions'] = {'😻': post.get('likes', 0), '🙀': 0, '😿': 0, '😾': 0, '🧠': 0}
        for e in ['😻', '🙀', '😿', '😾', '🧠']: 
            if e not in post['reactions']: post['reactions'][e] = 0

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
                        all_p = dm.load_data()
                        dm.save_data([x for x in all_p if x['id'] != post['id']])
                        st.rerun()

            if post.get('images'):
                valid_imgs = [img for img in post['images'] if img.startswith("http")]
                if valid_imgs:
                    if len(valid_imgs) == 1: st.image(valid_imgs[0], use_container_width=True)
                    else:
                        img_cols = st.columns(3)
                        for idx, img in enumerate(valid_imgs):
                            with img_cols[idx % 3]: st.image(img, use_container_width=True)
            elif post.get('image') and os.path.exists(post['image']): 
                st.image(post['image'], use_container_width=True)

            videos = post.get('video')
            if videos:
                if isinstance(videos, str): videos = [videos]
                for vid in videos:
                    if "drive.google.com" in vid and "preview" in vid:
                        st.markdown(f'<iframe src="{vid}" width="100%" height="300" style="border:none; border-radius:10px;"></iframe>', unsafe_allow_html=True)
                    elif vid.startswith("http") or os.path.exists(vid): st.video(vid)
            
            content_display = make_clickable(post['content']) 
            yt = re.search(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})', post['content'])
            if yt: st.video(f"https://youtu.be/{yt.group(6)}")
            
            st.markdown(f"""<div class="work-card-base" style="border-left: 5px solid {accent};">{content_display}</div>""", unsafe_allow_html=True)
            
            if post.get('price', 0) > 0:
                st.markdown(f"<div class='price-tag'>💰 ราคา: {post['price']:,} บาท</div>", unsafe_allow_html=True)
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
                        d = dm.load_data()
                        for p in d:
                            if p['id'] == post['id']:
                                if 'reactions' not in p: p['reactions'] = {'😻': 0, '🙀': 0, '😿': 0, '😾': 0, '🧠': 0}
                                for e_key in emojis: 
                                    if e_key not in p['reactions']: p['reactions'][e_key] = 0
                                
                                if user_react == emo:
                                    p['reactions'][emo] = max(0, p['reactions'][emo] - 1)
                                    del st.session_state['user_reactions'][post['id']]
                                else:
                                    if user_react and user_react in p['reactions']: 
                                        p['reactions'][user_react] = max(0, p['reactions'][user_react] - 1)
                                    p['reactions'][emo] += 1
                                    st.session_state['user_reactions'][post['id']] = emo
                                    
                                    if emo == '😻': st.balloons()
                                    elif emo == '🙀': st.snow()
                                    elif emo == '😿': st.toast("โอ๋ๆ ไม่ร้องนะคะคนเก่ง... 😿☔", icon="☔")
                                    elif emo == '😾': st.toast("ใจเย็นๆ นะคะพี่จ๋า! 🔥🔥", icon="🔥")
                                    elif emo == '🧠': st.toast("สุดยอด! บิ๊กเบรนมากค่ะ! ✨🧠✨", icon="🧠")
                                break
                        dm.save_data(d)
                        time.sleep(1.5); st.rerun()

            # --- ส่วน Comment (ปรับใหม่ให้ซ่อนถ้าไม่ Login) ---
            is_logged_in = st.session_state.get('discord_user') or st.session_state.get('is_admin')

            with st.expander(f"💬 ความคิดเห็น ({len(post['comments'])})"):
                # กรณี: ยังไม่ Login (ซ่อนคอมเมนต์แบบยั่วๆ)
                if not is_logged_in:
                    st.markdown("""
                    <div style="background: repeating-linear-gradient(45deg, #161B22, #161B22 10px, #0d1117 10px, #0d1117 20px); 
                                padding: 20px; text-align: center; border-radius: 10px; border: 1px dashed #A370F7; color: #8B949E;">
                        <h3>🔒 ความลับของชาวแก๊ง!</h3>
                        <p>มีบทสนทนาลับๆ ซ่อนอยู่ {num} ข้อความ...</p>
                        <p style="font-size: 12px;">(Login Discord ที่เมนูซ้ายมือเพื่อปลดล็อคและร่วมวงสนทนา)</p>
                    </div>
                    """.format(num=len(post['comments'])), unsafe_allow_html=True)
                
                # กรณี: Login แล้ว (โชว์ตามปกติ)
                else:
                    if post['comments']:
                        for i, c in enumerate(post['comments']):
                            is_admin_comment = c.get('is_admin', False)
                            if is_admin_comment:
                                st.markdown(f"""<div class='admin-comment-box'><b>👑 {c['user']} (Owner):</b> {c['text']}</div>""", unsafe_allow_html=True)
                                if c.get('image'):
                                    if c['image'].startswith("http"): st.image(c['image'], width=200)
                                    elif os.path.exists(c['image']): st.image(c['image'], width=200)
                            else:
                                st.markdown(f"<div class='comment-box'><b>{c['user']}:</b> {c['text']}</div>", unsafe_allow_html=True)
                            
                            # ปุ่มลบของ Admin
                            if st.session_state['is_admin'] and st.button("ลบ", key=f"dc_{post['id']}_{i}"):
                                d = dm.load_data()
                                for x in d:
                                    if x['id'] == post['id']: x['comments'].pop(i); break
                                dm.save_data(d); st.rerun()

                    # ฟอร์มคอมเมนต์ (เฉพาะคน Login แล้ว)
                    admin_cmt_img_link = None
                    if st.session_state['is_admin']:
                        st.caption("👑 ตอบกลับในฐานะ Admin")
                        admin_cmt_img_link = st.text_input("ลิงก์รูป (Google Drive/Web)", key=f"ci_{post['id']}", placeholder="https://...")

                    with st.form(key=f"cf_{post['id']}"):
                        if st.session_state['is_admin']:
                            u = st.text_input("ชื่อ (Admin)", value="Dearluxion")
                        else:
                            d_name = st.session_state['discord_user']['username']
                            st.text_input("ชื่อผู้ใช้", value=d_name, disabled=True)
                            u = d_name

                        t = st.text_input("ข้อความ", placeholder="แสดงความคิดเห็น...", label_visibility="collapsed")
                        
                        if st.form_submit_button("ส่ง"):
                            now = time.time()
                            if not st.session_state['is_admin'] and now - st.session_state['last_comment_time'] < 35:
                                st.toast(f"🧚‍♀️ ไมล่า: รออีก {35 - int(now - st.session_state['last_comment_time'])} วินาทีก่อนนะ!", icon="⛔")
                            elif t:
                                cmt_img_val = None
                                if admin_cmt_img_link: cmt_img_val = convert_drive_link(admin_cmt_img_link)
                                d = dm.load_data()
                                for x in d:
                                    if x['id'] == post['id']: 
                                        x['comments'].append({"user": u, "text": t, "is_admin": st.session_state['is_admin'], "image": cmt_img_val})
                                        break
                                dm.save_data(d)
                                if not st.session_state['is_admin']: st.session_state['last_comment_time'] = now 
                                st.rerun()
else:
    # เพิ่มเงื่อนไขว่าต้องไม่ใช่หน้า Crypto ด้วย (not st.session_state['show_crypto'])
    if not st.session_state['show_shop'] and not st.session_state['show_crypto']: 
        st.info("ยังไม่มีโพสต์ครับ")

st.markdown("<br><center><small style='color:#A370F7'>Small Group by Dearluxion © 2025</small></center>", unsafe_allow_html=True)