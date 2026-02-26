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
from utils import (
    convert_drive_link,
    convert_drive_video_link,
    make_clickable,
    send_post_to_discord,
    exchange_code_for_token,
    get_discord_user,
    send_crypto_report_to_discord,
    append_crypto_analysis_to_gsheet,
    append_crypto_memory_to_gsheet,
    build_crypto_memory_context,
)
import data_manager as dm
import sidebar_manager as sm
import ai_manager as ai
import prediction_engine as pe
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
if 'realtime_analysis' not in st.session_state: st.session_state['realtime_analysis'] = False
if 'analyze_all' not in st.session_state: st.session_state['analyze_all'] = False
if 'realtime_all_request' not in st.session_state: st.session_state['realtime_all_request'] = False
if 'realtime_all_result' not in st.session_state: st.session_state['realtime_all_result'] = None
if 'realtime_all_summary' not in st.session_state: st.session_state['realtime_all_summary'] = None

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

            # [NEW] คุมจำนวนหน้าม้า AI ก่อนโพสต์
            num_bots_ui = st.slider("🤖 จำนวนหน้าม้า AI (คอมเมนต์จำลอง)", min_value=0, max_value=80, value=25, step=1, help="0 = ไม่เรียกหน้าม้า (โพสต์เงียบๆ)")

            # [NEW] เลือกจำนวนรูปที่จะส่งเข้า Discord (แก้ปัญหาลิงก์รูปไม่เด้ง)
            max_images_to_discord = st.slider("🖼️ ส่งรูปเข้า Discord กี่รูป", min_value=0, max_value=10, value=1, step=1, help="ระบบจะ 'แนบไฟล์' เพื่อให้ Discord แสดงรูปชัวร์ (เสถียรกว่าลิงก์)")

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
                    if num_bots_ui and int(num_bots_ui) > 0:
                        # ส่งทั้ง Text, รูป, วิดีโอ Drive (ถ้ามี) และ YouTube URL ไปให้ AI
                        ai_engagements = ai.generate_post_engagement(
                            new_desc,
                            main_img_url,
                            main_yt_url,
                            num_bots=num_bots_ui,
                            media_url=(final_vid_links[0] if (not main_img_url and final_vid_links) else None),
                        )
                    else:
                        ai_engagements = []
                
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
                        send_post_to_discord(new_post, max_images=max_images_to_discord, send_comments=False)
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
                send_post_to_discord(p, send_comments=False)
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
        st.markdown("## 📈 ศูนย์บัญชาการคริปโต (Crypto Tactical War Room)")
        st.caption("สรุปให้อ่านง่ายก่อน แล้วค่อยเจาะลึกแบบ AI ทีละชั้น | หน่วยราคา: THB")
        
        # รายชื่อเหรียญครบ 8 ตัว
        coin_list = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "PEPE", "SHIB"]
        
        col_c1, col_c2 = st.columns([2, 1])
        with col_c1:
            coin_select = st.selectbox("เลือกเหรียญที่จะวิเคราะห์แบบจริงจัง:", coin_list)
        with col_c2:
            if st.button("🎯 วิเคราะห์เหรียญนี้", type="primary", use_container_width=True):
                st.session_state['trigger_analysis'] = True
                st.session_state['analyze_all'] = False # Reset โหมดเหมา
        
        # ปุ่มวิเคราะห์เหมาเข่ง
        if st.button("🚀 สแกนทั้ง 8 เหรียญ (Market Radar)", use_container_width=True, key="btn_batch_top"):
            st.session_state['analyze_all'] = True
            st.session_state['trigger_analysis'] = False
            st.rerun()
        
        # ========== ✅ วิเคราะห์ Real-Time แบบ “ครั้งเดียว” (Admin Only) ==========
        st.markdown("---")
        if st.session_state.get('is_admin'):
            # ปุ่มเดียว: กดแล้ว “ดึงข้อมูลสด + วิเคราะห์ครบ 8 เหรียญ” 1 รอบ แล้วเก็บผลไว้โชว์แบบนิ่งๆ
            c_rt1, c_rt2 = st.columns([2, 1])
            with c_rt1:
                if st.button("🔴 ดึงสด 8 เหรียญรอบเดียว (Real-Time Radar)", type="primary", use_container_width=True, key="btn_realtime_all_once"):
                    st.session_state['realtime_all_request'] = True
                    st.rerun()

            with c_rt2:
                if st.button("🧹 ล้างผล Real-Time", use_container_width=True, key="btn_clear_realtime_all"):
                    st.session_state['realtime_all_result'] = None
                    st.session_state['realtime_all_request'] = False
                    st.rerun()

            realtime_all_output = st.container()

            # ---- Run (only when requested) ----
            if st.session_state.get('realtime_all_request'):
                try:
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for idx, c_symbol in enumerate(coin_list):
                        status_text.text(f"⏱️ กำลังดึงข้อมูล Real-Time + วิเคราะห์ {c_symbol} ({idx+1}/{len(coin_list)})...")

                        # ดึงข้อมูลแบบเรียลไทม์ (กรอบสั้น) + ข่าว + Fear/Greed
                        live_df = ce.get_crypto_data(c_symbol, period="1d", interval="1h")
                        live_news = ce.get_crypto_news(c_symbol)
                        live_fg = ce.get_fear_and_greed()

                        if live_df is None or len(live_df) == 0:
                            results.append({
                                "symbol": c_symbol,
                                "error": "❌ ไม่สามารถดึงข้อมูลกราฟ Real-Time ได้",
                                "analysis": None,
                                "latest_price": None,
                                "indicators": {}
                            })
                            progress_bar.progress((idx + 1) / len(coin_list))
                            continue

                        latest = live_df.iloc[-1]
                        # ใช้ safe_float กันค่า None (บางเหรียญ/บางช่วงข้อมูลจะว่าง)
                        latest_price = ai.safe_float(latest.get('Close', 0), 0.0)

                        # ดึงค่าที่มีอยู่ (ถ้าไม่มีให้ใส่ค่าเริ่มต้น) — ใช้ safe_float เพื่อกัน None
                        rsi_val = ai.safe_float(latest.get('RSI', 50), 50.0) if 'RSI' in live_df.columns else 50.0
                        macd_val = ai.safe_float(latest.get('MACD', 0), 0.0) if 'MACD' in live_df.columns else 0.0
                        macd_signal = ai.safe_float(latest.get('MACD_SIGNAL', 0), 0.0) if 'MACD_SIGNAL' in live_df.columns else 0.0
                        adx_val = ai.safe_float(latest.get('ADX', 20), 20.0) if 'ADX' in live_df.columns else 20.0
                        atr_val = ai.safe_float(latest.get('ATR', 0), 0.0) if 'ATR' in live_df.columns else 0.0
                        stoch_k = ai.safe_float(latest.get('Stoch_K', 50), 50.0) if 'Stoch_K' in live_df.columns else 50.0

                        obv_slope = "N/A"
                        if 'OBV_Slope' in live_df.columns:
                            v_obv = ai.safe_float(latest.get('OBV_Slope', 0), 0.0)
                            obv_slope = "เงินไหลเข้า (Positive)" if v_obv > 0 else "เงินไหลออก (Negative)"

                        # Pivot / Support / Resistance ถ้ามี — ใช้ safe_float กัน None
                        pivot_p = ai.safe_float(latest.get('Pivot_P', latest_price), latest_price) if 'Pivot_P' in live_df.columns else latest_price
                        pivot_s1 = ai.safe_float(latest.get('Pivot_S1', latest_price * 0.95), latest_price * 0.95) if 'Pivot_S1' in live_df.columns else latest_price * 0.95
                        pivot_r1 = ai.safe_float(latest.get('Pivot_R1', latest_price * 1.05), latest_price * 1.05) if 'Pivot_R1' in live_df.columns else latest_price * 1.05
                        support = ai.safe_float(latest.get('Support_Level', latest_price * 0.95), latest_price * 0.95) if 'Support_Level' in live_df.columns else latest_price * 0.95
                        resistance = ai.safe_float(latest.get('Resistance_Level', latest_price * 1.05), latest_price * 1.05) if 'Resistance_Level' in live_df.columns else latest_price * 1.05

                        indicators = {
                            "rsi": rsi_val,
                            "stoch_k": stoch_k,
                            "macd": macd_val,
                            "macd_signal": macd_signal,
                            "adx": adx_val,
                            "atr": atr_val,
                            "obv_slope": obv_slope,
                            "pivot_p": pivot_p,
                            "pivot_s1": pivot_s1,
                            "pivot_r1": pivot_r1,
                            "support": support,
                            "resistance": resistance
                        }

                        analysis_result = None
                        if ai_available and crypto_available:
                            # 🧠 โหลด Memory และสตรีมให้เห็น AI คุยกันเองระหว่างรอ (แบบย่อ)
                            memory_ctx = ""
                            try:
                                memory_ctx = build_crypto_memory_context(c_symbol)
                            except Exception:
                                memory_ctx = ""

                            if hasattr(ai, "analyze_crypto_reflection_stream"):
                                collector = {"analyst": "", "critic": "", "final": ""}
                                mini_box = st.empty()

                                for ev in ai.analyze_crypto_reflection_stream(
                                    c_symbol, latest_price, indicators, live_news, live_fg, memory_context=memory_ctx
                                ):
                                    et = (ev or {}).get("type")
                                    if et == "status":
                                        mini_box.markdown(f"🗣️ {ev.get('text','')}")
                                    elif et == "message":
                                        sp = ev.get("speaker", "")
                                        tx = (ev.get("text","") or "").strip()
                                        if sp == "Analyst":
                                            collector["analyst"] = tx
                                            mini_box.markdown(f"🧚‍♀️ **Analyst:** {tx[:220]}{'...' if len(tx)>220 else ''}")
                                        elif sp == "Critic":
                                            collector["critic"] = tx
                                            mini_box.markdown(f"🍸 **Critic:** {tx[:220]}{'...' if len(tx)>220 else ''}")
                                        elif sp == "Final":
                                            collector["final"] = tx
                                            mini_box.markdown(f"🧬 **Final:** {tx[:220]}{'...' if len(tx)>220 else ''}")
                                    elif et == "error":
                                        mini_box.error(ev.get("text",""))

                                mini_box.empty()

                                analysis_pack = {
                                    "final": collector.get("final",""),
                                    "analyst": collector.get("analyst",""),
                                    "critic": collector.get("critic",""),
                                    "meta": {"coin": c_symbol, "generated_at": datetime.datetime.now().isoformat(timespec="seconds")},
                                }
                            else:
                                analysis_pack = ai.analyze_crypto_reflection_mode(
                                    c_symbol, latest_price, indicators, live_news, live_fg, return_steps=True, memory_context=memory_ctx
                                )
                            if isinstance(analysis_pack, dict):
                                analysis_result = analysis_pack.get('final', '')
                                debate_pack = {'analyst': analysis_pack.get('analyst', ''), 'critic': analysis_pack.get('critic', '')}
                            else:
                                analysis_result = analysis_pack
                                debate_pack = None
                        else:
                            analysis_result = "⚠️ ระบบ AI/crypto ยังไม่พร้อม จึงสรุปได้แค่ข้อมูลตลาดเบื้องต้น"
                            debate_pack = None

                        # --- [NEW] ทำให้ผล Real-Time โชว์ในจุดเดียวกับปุ่มวิเคราะห์ธรรมดา ---
                        # 1) บันทึกเข้า Cache (เหมือนปุ่มวิเคราะห์ปกติ)
                        try:
                            dm.update_crypto_cache(c_symbol, analysis_result)
                        except Exception as _e:
                            print(f"❌ Cache update (realtime) failed: {_e}")

                        # 2) Log เข้า Google Sheets
                        try:
                            append_crypto_analysis_to_gsheet(
                                mode="realtime_once",
                                symbol=c_symbol,
                                price=latest_price,
                                analysis_text=analysis_result,
                                indicators=indicators,
                                news_count=len(live_news) if live_news else 0,
                                fg=live_fg,
                                generated_at=datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                        except Exception as _e:
                            print(f"❌ Sheets log (realtime) failed: {_e}")

                        # 3) ส่งเข้า Discord (ทุกระบบ)
                        try:
                            c_webhook = st.secrets.get("general", {}).get("crypto_webhook", "")
                            if c_webhook:
                                send_crypto_report_to_discord(c_webhook, c_symbol, latest_price, analysis_result)
                        except Exception as _e:
                            print(f"❌ Discord send (realtime) failed: {_e}")

                        results.append({
                            "symbol": c_symbol,
                            "error": None,
                            "analysis": analysis_result,
                            "debate": debate_pack,
                            "latest_price": latest_price,
                            "indicators": indicators,
                            "news_count": len(live_news) if live_news else 0,
                            "fg": live_fg
                        })

                        progress_bar.progress((idx + 1) / len(coin_list))

                    status_text.empty()
                    progress_bar.empty()

                    # เก็บผลไว้โชว์แบบนิ่งๆ จนกว่าจะกดใหม่/ล้าง
                    st.session_state['realtime_all_result'] = {
                        "generated_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "results": results
                    }
                except Exception as e:
                    st.session_state['realtime_all_result'] = {
                        "generated_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "results": [],
                        "error": str(e)
                    }
                finally:
                    st.session_state['realtime_all_request'] = False
                    st.rerun()

            # ---- Display (static) ----
            with realtime_all_output:
                rt_pack = st.session_state.get('realtime_all_result')
                if rt_pack:
                    st.markdown(f"### ✅ ผล Real-Time (ครั้งเดียว) — อัปเดตเมื่อ {rt_pack.get('generated_at','')}")
                    if rt_pack.get('error'):
                        st.error(f"⚠️ Error: {rt_pack['error']}")


                    # =========================
                    # 🧾 Summary (หลังวิเคราะห์ครบ 8 เหรียญ)
                    # =========================
                    def _rt_status_key(ind: dict):
                        """คัดกรองสถานะแบบเร็ว (ไม่เรียก AI ซ้ำ)"""
                        try:
                            rsi = float(ind.get("rsi", 50))
                        except:
                            rsi = 50.0
                        try:
                            macd = float(ind.get("macd", 0))
                        except:
                            macd = 0.0
                        try:
                            sig = float(ind.get("macd_signal", 0))
                        except:
                            sig = 0.0
                        try:
                            adx = float(ind.get("adx", 20))
                        except:
                            adx = 20.0
                        obv = str(ind.get("obv_slope", "")).lower()

                        # Trap: ราคาดูดีแต่เงินไหลออก
                        if ("ไหลออก" in obv) and (rsi >= 55):
                            return "TRAP"

                        # Very bullish: oversold + เริ่มกลับตัว + มี trend
                        if (rsi <= 35) and (macd > sig) and (adx >= 20):
                            return "VERY_BULLISH"

                        # Bullish: momentum ดี
                        if (macd > sig) and (rsi >= 45) and (adx >= 18):
                            return "BULLISH"

                        # Bearish: momentum เสีย หรือ overbought + อ่อนแรง
                        if (macd < sig) and (adx >= 18):
                            return "BEARISH"
                        if (rsi >= 70) and (macd <= sig):
                            return "BEARISH"

                        return "NEUTRAL"

                    _rt_status_map = {
                        "BEARISH": {"icon": "🔴", "title": "ยังไม่ควรซื้อ", "action": "รอให้มีสัญญาณกลับตัว/ยืนแนวรับก่อน"},
                        "NEUTRAL": {"icon": "🟡", "title": "ยังไม่ใช่ตอนนี้", "action": "รอดูทิศทางให้ชัดก่อนค่อยเข้า"},
                        "BULLISH": {"icon": "🟢", "title": "เริ่มน่าสนใจ", "action": "ทยอยสะสม + ตั้ง Stop Loss"},
                        "VERY_BULLISH": {"icon": "🔥", "title": "น่าเก็บมาก", "action": "เข้าเป็นไม้ ห้าม All-in"},
                        "TRAP": {"icon": "❌", "title": "อย่าเข้า", "action": "เสี่ยงโดนทุบ/กับดักราคา ไม่ควร FOMO"},
                    }

                    c_s1, c_s2 = st.columns([2, 1])
                    with c_s1:
                        if st.button("🧾 สรุปคำแนะนำ 8 เหรียญ (จากรอบนี้)", use_container_width=True, key="btn_rt_summary"):
                            lines = []
                            for it in rt_pack.get('results', []):
                                if it.get('error'):
                                    continue
                                s = it.get('symbol')
                                p = float(it.get('latest_price', 0) or 0)
                                ind = it.get('indicators', {}) or {}
                                key = _rt_status_key(ind)
                                meta = _rt_status_map.get(key, _rt_status_map["NEUTRAL"])

                                pf = "{:,.4f}" if s in ["SHIB", "PEPE", "DOGE"] else "{:,.2f}"
                                lines.append(f"{meta['icon']} **{s}**: **{meta['title']}** ตอนราคา **฿{pf.format(p)}** — {meta['action']}")
                            st.session_state['realtime_all_summary'] = {
                                "generated_at": rt_pack.get('generated_at', ''),
                                "lines": lines
                            }

                    with c_s2:
                        if st.button("🧹 ล้างสรุป", use_container_width=True, key="btn_rt_summary_clear"):
                            st.session_state['realtime_all_summary'] = None

                    summ_pack = st.session_state.get('realtime_all_summary')
                    if summ_pack and summ_pack.get('lines'):
                        st.markdown(f"#### 🧾 สรุป (อัปเดตเมื่อ {summ_pack.get('generated_at','')})")
                        for ln in summ_pack['lines']:
                            st.markdown(ln)

                    for item in rt_pack.get('results', []):
                        sym = item.get('symbol')
                        if item.get('error'):
                            with st.expander(f"💎 {sym} (Real-Time)", expanded=False):
                                st.error(item['error'])
                            continue

                        latest_price = item.get('latest_price', 0)
                        price_fmt = "{:,.4f}" if sym in ["SHIB", "PEPE", "DOGE"] else "{:,.2f}"

                        with st.expander(f"🔴 {sym} Real-Time | ฿{price_fmt.format(latest_price)}", expanded=False):
                            # Quick metrics
                            k1, k2, k3, k4 = st.columns(4)
                            try:
                                k1.metric("💰 ราคา", f"฿{price_fmt.format(latest_price)}")
                                k2.metric("📊 RSI", item['indicators'].get("rsi", "N/A"))
                                k3.metric("⚡ MACD", item['indicators'].get("macd", "N/A"))
                                fg_val = item.get("fg", {}).get("value", "N/A")
                                fg_cls = item.get("fg", {}).get("value_classification", "N/A")
                                k4.metric("😨 Fear/Greed", str(fg_val), str(fg_cls))
                            except:
                                pass

                            st.caption(f"📰 ข่าวล่าสุด: {item.get('news_count', 0)} รายการ")
                            try:
                                rt_brief = ai.build_trade_brief(sym, latest_price, item.get('indicators', {}) or {}, item.get('analysis', ''))
                                st.markdown(ai.render_trade_brief_markdown(rt_brief))
                            except Exception as _rt_brief_err:
                                st.caption(f"ข้ามสรุปย่ออัตโนมัติ: {_rt_brief_err}")
                            deb = item.get("debate") or {}
                            if deb:
                                t_final, t_analyst, t_critic = st.tabs(["🧠 Final", "🧚‍♀️ Analyst", "🍸 Critic"])
                                with t_final:
                                    st.markdown(item.get('analysis', ''))
                                with t_analyst:
                                    st.markdown(deb.get("analyst", ""))
                                with t_critic:
                                    st.markdown(deb.get("critic", ""))
                            else:
                                st.markdown(item.get('analysis', ''))

        else:
            st.info("🔒 ปุ่ม Real-Time (ครั้งเดียว) สำหรับแอดมินเท่านั้น")

        # =========================================================
        # TABS: Analysis & Backtest
        # =========================================================
        # Helper แปลผล Fear Greed (แปลไทย) - สำหรับ Tab Analysis
        def translate_fng(classification):
            mapping = {
                "Extreme Fear": "กลัวสุดขีด (Extreme Fear)",
                "Fear": "กลัว (Fear)",
                "Neutral": "เฉยๆ (Neutral)",
                "Greed": "โลภ (Greed)",
                "Extreme Greed": "โลภสุดขีด (Extreme Greed)"
            }
            return mapping.get(classification, classification)
        
        tab_analysis, tab_backtest = st.tabs(["📊 วิเคราะห์ตลาด", "⚖️ ตรวจการบ้าน (Backtest)"])
        
        with tab_analysis:
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
                    st.markdown(f"### 🧠 ศูนย์วิเคราะห์เชิงลึก - {coin_select}")
                    
                    with st.chat_message("ai", avatar="👁️"):
                        # 1. เช็ค Cache ก่อน
                        cached_data = dm.get_crypto_cache(coin_select)
                        
                        if cached_data:
                            # เจอข้อมูลของวันนี้ -> แสดงเลย ไม่ต้องโหลด
                            st.success(f"⚡ โหลดข้อมูลวิเคราะห์ประจำวันสำเร็จ (อัปเดตเมื่อ: {cached_data['updated_at']} น.)")
                            st.markdown(cached_data['analysis'])
                            st.caption("ℹ️ นี่คือผลที่เคยวิเคราะห์ไว้แล้ววันนี้ ระบบจึงดึงมาให้ทันทีเพื่อประหยัดทรัพยากร")
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
                                    # 🧠 ใช้ Reflection Mode 3-Step (Chain of Thought) แบบใหม่
                                    # สร้าง Progress Bar จำลองการคิด
                                    thinking_container = st.container()
                                    with thinking_container:
                                        thinking_bar = st.progress(0)
                                        status_box = st.empty()
                                        
                                        # STEP 1: เริ่มกระบวนการ
                                        status_box.markdown("🤔 **Phase 1:** Myla 🧚‍♀️ กำลังสแกนหาโอกาสทำกำไร...")
                                        thinking_bar.progress(25)
                                        time.sleep(0.5)
                                        
                                        # STEP 2: ส่งไปให้ Function ใหม่ทำงาน (ซึ่งข้างในมันจะยิง API 3 รอบ)
                                        status_box.markdown("🔥 **Phase 2:** Ariel 🍸 กำลังจับผิดและประเมินความเสี่ยง (Deep Critique)...")
                                        thinking_bar.progress(50)
                                        
                                        # 🧠 โหลด Memory (บทเรียนจากความผิดพลาด) แล้วสตรีมให้เห็น AI คุยกันเองขณะรอ
                                        memory_ctx = ""
                                        try:
                                            memory_ctx = build_crypto_memory_context(coin_select)
                                        except Exception as _e:
                                            memory_ctx = f"[Memory] โหลดบทเรียนไม่สำเร็จ: {_e}"

                                        analysis_pack = None
                                        dialogue_live = st.container()

                                        if hasattr(ai, "analyze_crypto_reflection_stream"):
                                            collector = {"analyst": "", "critic": "", "final": ""}
                                            if memory_ctx:
                                                with dialogue_live.chat_message("assistant", avatar="🧠"):
                                                    st.markdown("### 🧠 Memory ที่ระบบจำได้ (บทเรียนเก่า)")
                                                    st.code(memory_ctx)

                                            for ev in ai.analyze_crypto_reflection_stream(
                                                coin_select, latest_price, indicators, news, fg_index, memory_context=memory_ctx
                                            ):
                                                et = (ev or {}).get("type")
                                                if et == "status":
                                                    status_box.markdown(ev.get("text", ""))
                                                    ph = int(ev.get("phase", 0) or 0)
                                                    thinking_bar.progress(25 if ph == 1 else 55 if ph == 2 else 85)
                                                elif et == "memory":
                                                    with dialogue_live.chat_message("assistant", avatar="🧠"):
                                                        st.code(ev.get("text", ""))
                                                elif et == "message":
                                                    sp = ev.get("speaker", "")
                                                    tx = ev.get("text", "")
                                                    if sp == "Analyst":
                                                        collector["analyst"] = tx
                                                        with dialogue_live.chat_message("assistant", avatar="🧚‍♀️"):
                                                            st.markdown("### 🧚‍♀️ Analyst (Myla) — Draft")
                                                            st.markdown(tx)
                                                    elif sp == "Critic":
                                                        collector["critic"] = tx
                                                        with dialogue_live.chat_message("assistant", avatar="🍸"):
                                                            st.markdown("### 🍸 Critic (Ariel) — Risk Check")
                                                            st.markdown(tx)
                                                    elif sp == "Final":
                                                        collector["final"] = tx
                                                        with dialogue_live.chat_message("assistant", avatar="🧬"):
                                                            st.markdown("### 🧬 God Mode — Final")
                                                            st.markdown(tx)
                                                elif et == "error":
                                                    raise Exception(ev.get("text", "Unknown stream error"))

                                            analysis_pack = {
                                                "final": collector.get("final", ""),
                                                "analyst": collector.get("analyst", ""),
                                                "critic": collector.get("critic", ""),
                                                "meta": {"coin": coin_select, "generated_at": datetime.datetime.now().isoformat(timespec="seconds")},
                                            }
                                        else:
                                            analysis_pack = ai.analyze_crypto_reflection_mode(
                                                coin_select, latest_price, indicators, news, fg_index, return_steps=True, memory_context=memory_ctx
                                            )

                                        analysis_result = analysis_pack.get("final", "") if isinstance(analysis_pack, dict) else str(analysis_pack)

                                        status_box.markdown("✨ **Phase 3:** สรุปผลกลยุทธ์ God Mode เสร็จสิ้น!")
                                        thinking_bar.progress(100)
                                        time.sleep(0.5)
                                        
                                        # ล้าง Status Bar แล้วโชว์ผลลัพธ์
                                        status_box.empty()
                                        thinking_bar.empty()
                                    
                                    # บันทึกลง Cache ทันที
                                    dm.update_crypto_cache(coin_select, analysis_result)

                                    # --- [NEW] Log ลง Google Sheets ---
                                    try:
                                        append_crypto_analysis_to_gsheet(
                                            mode="single",
                                            symbol=coin_select,
                                            price=latest_price,
                                            analysis_text=analysis_result,
                                            indicators=indicators,
                                            news_count=len(news) if news else 0,
                                            fg=fg_index,
                                            generated_at=datetime.datetime.now().isoformat(timespec="seconds"),
                                        )
                                    except Exception as _e:
                                        print(f"❌ Sheets log (single) failed: {_e}")
                                    
                                    # ✅ แสดงผลแบบแท็บ (Final / Analyst / Critic)
                                    if isinstance(analysis_pack, dict) and (analysis_pack.get("analyst") or analysis_pack.get("critic")):
                                        t_final, t_analyst, t_critic = st.tabs(["🧠 Final", "🧚‍♀️ Analyst", "🍸 Critic"])
                                        with t_final:
                                            try:
                                                brief = ai.build_trade_brief(coin_select, latest_price, indicators, analysis_pack.get("final", ""), memory_ctx)
                                                st.markdown(ai.render_trade_brief_markdown(brief))
                                                st.markdown("---")
                                            except Exception as _brief_err:
                                                st.caption(f"ข้ามสรุปย่ออัตโนมัติ: {_brief_err}")
                                            st.markdown(analysis_pack.get("final", ""))
                                        with t_analyst:
                                            st.markdown(analysis_pack.get("analyst", ""))
                                        with t_critic:
                                            st.markdown(analysis_pack.get("critic", ""))
                                    else:
                                        try:
                                            brief = ai.build_trade_brief(coin_select, latest_price, indicators, analysis_result, memory_ctx)
                                            st.markdown(ai.render_trade_brief_markdown(brief))
                                            st.markdown("---")
                                        except Exception as _brief_err:
                                            st.caption(f"ข้ามสรุปย่ออัตโนมัติ: {_brief_err}")
                                        st.markdown(analysis_result)

                                    st.caption(f"🧠 วิเคราะห์แบบ Deep Reflection (3-Step Reasoning) | เวลา: {datetime.datetime.now().strftime('%H:%M')} น.")

                                    # 🧠 บันทึกบทเรียนให้ระบบจำ (Memory) — เพื่อให้รอบหน้ามีคำเตือนที่ฉลาดขึ้น
                                    with st.expander("🧠 บันทึกบทเรียนให้ระบบจำ (หลังเทรดจริง)", expanded=False):
                                        with st.form(f"mem_form_{coin_select}"):
                                            outcome = st.selectbox("ผลลัพธ์รอบนี้", ["WIN", "LOSE", "DRAW"], index=1)
                                            self_score = st.slider("ให้คะแนนตัวเอง (0-100)", 0, 100, 70)
                                            mistakes = st.text_area(
                                                "ผิดพลาด/บทเรียน (Mistakes)",
                                                placeholder="เช่น FOMO ตอน RSI สูง / SL แคบเกิน / เข้าไม้ใหญ่เกิน / ไม่รอ Confirm",
                                                height=110
                                            )
                                            fix_plan = st.text_area(
                                                "แผนแก้ (Fix Plan) — รอบหน้าจะทำยังไงไม่ให้พลาดซ้ำ",
                                                placeholder="เช่น รอแท่งยืนยัน 1 แท่ง, แบ่งไม้ 3 ไม้, ใช้ ATR คำนวณ SL, ห้ามไล่ราคา",
                                                height=110
                                            )
                                            tags = st.text_input("Tags (คั่นด้วย comma)", placeholder="FOMO,RSI,OBV,news,breakout")
                                            if st.form_submit_button("💾 บันทึก Memory"):
                                                try:
                                                    append_crypto_memory_to_gsheet(
                                                        symbol=coin_select,
                                                        outcome=outcome,
                                                        self_score=float(self_score),
                                                        mistakes=mistakes.strip(),
                                                        fix_plan=fix_plan.strip(),
                                                        tags=tags.strip(),
                                                        mode="manual",
                                                        logged_at=datetime.datetime.now().isoformat(timespec="seconds"),
                                                    )
                                                    st.toast("✅ บันทึกบทเรียนแล้ว! รอบหน้าระบบจะเอาไปเตือนตัวเองก่อนเชียร์ 😎", icon="🧠")
                                                except Exception as _e:
                                                    st.error(f"บันทึก Memory ไม่สำเร็จ: {_e}")
                                    
                                    # --- [NEW CODE] แทรกตรงนี้เพื่อส่งเข้า Discord ---
                                    # ดึง Webhook จาก Secrets
                                    c_webhook = st.secrets.get("general", {}).get("crypto_webhook", "")
                                    if c_webhook:
                                        with st.spinner("🚀 กำลังส่งสัญญาณเข้า Discord..."):
                                            from utils import send_crypto_report_to_discord
                                            send_crypto_report_to_discord(c_webhook, coin_select, latest_price, analysis_result)
                                            st.toast(f"ส่งผลวิเคราะห์ {coin_select} เข้าห้อง Discord แล้ว!", icon="📢")
                                    # -----------------------------------------------
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
            st.markdown("---")
            st.markdown("### 🚀 วิเคราะห์เหมาเข่ง 8 เหรียญ (Batch Mode)")
            if st.button("🚀 วิเคราะห์ทั้ง 8 เหรียญ โปรดของท่านเดียร์", use_container_width=True, key="btn_batch_tab"):
                st.session_state['analyze_all'] = True
                st.rerun()

        # =========================================================
        # BACKTEST TAB
        # =========================================================
        with tab_backtest:
            st.markdown("### ⚖️ ตารางคะแนนความแม่นของระบบ (Reality Scoreboard)")
            st.caption("เช็กว่าที่ระบบเคยแนะนำไว้ ตรงกับราคาจริงแค่ไหน เพื่อใช้เป็นบทเรียนก่อนเทรดรอบต่อไป")
            
            history = dm.get_today_summary()
            if history:
                for h in history:
                    try:
                        score = int(str(h.get('score', '0')).replace("%", "").strip())
                    except:
                        score = 0
                    color = "green" if score >= 80 else "orange" if score >= 40 else "red"
                    st.markdown(f"""<div style="background:#161B22; padding:15px; border-radius:10px; margin-bottom:10px; border-left: 5px solid {color};"><div style="display:flex; justify-content:space-between;"><h4 style="margin:0;">{h.get('symbol', 'N/A')} ({h.get('signal', 'N/A')})</h4><span style="color:{color}; font-weight:bold;">{h.get('status', 'PENDING')} ({h.get('score', '0')})</span></div><small>Entry: {h.get('entry', 'N/A')} | Target: {h.get('target', 'N/A')} | Close: {h.get('close_price', 'N/A')}</small></div>""", unsafe_allow_html=True)
            else:
                st.info("ยังไม่มีผลสรุปของวันนี้ (รอตรวจตอน 21:00 น.)")

            st.markdown("---")
            if st.button("🔄 รันระบบตรวจการบ้าน (Daily Check)", type="primary", use_container_width=True):
                with st.spinner("👨‍⚖️ AI Judge กำลังตรวจข้อสอบ..."):
                    wh_url = st.secrets.get("general", {}).get("crypto_webhook", "")
                    res = pe.check_accuracy_and_broadcast(wh_url)
                    st.success(res)
                    time.sleep(2)
                    st.rerun()

        # =========================================================
        # CASE B Background: วิเคราะห์รวดเดียว (Batch Mode)
        # =========================================================
        if st.session_state.get('analyze_all'):
            st.markdown("### 🚀 รายงานสแกนตลาด 8 เหรียญ (Market Radar)")
            if st.button("❌ ปิดโหมดวิเคราะห์รวม"):
                st.session_state['analyze_all'] = False
                st.rerun()

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # วนลูปวิเคราะห์ทีละตัว
            for idx, c_symbol in enumerate(coin_list):
                status_text.text(f"กำลังสแกนตลาดและสรุปจุดเข้า {c_symbol} ({idx+1}/{len(coin_list)})...")
                
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
                                
                                # 🧠 สั่ง AI วิเคราะห์สด (Reflection Mode 3-Step)
                                res_batch = ai.analyze_crypto_reflection_mode(c_symbol, last_p, indicators_b, "วิเคราะห์ตามกราฟเทคนิคอลล่าสุด", {"value":"50", "value_classification":"Neutral"})
                                try:
                                    batch_brief = ai.build_trade_brief(c_symbol, last_p, indicators_b, res_batch)
                                    st.markdown(ai.render_trade_brief_markdown(batch_brief))
                                    st.markdown("---")
                                except Exception as _batch_brief_err:
                                    st.caption(f"ข้ามสรุปย่ออัตโนมัติ: {_batch_brief_err}")
                                st.markdown(res_batch)
                                
                                # --- [จุดที่เพิ่ม] บันทึกลง Google Sheets ทันที ---
                                dm.update_crypto_cache(c_symbol, res_batch)

                                # --- [NEW] Log ลง Google Sheets (Batch Mode) ---
                                try:
                                    append_crypto_analysis_to_gsheet(
                                        mode="batch",
                                        symbol=c_symbol,
                                        price=last_p,
                                        analysis_text=res_batch,
                                        indicators=indicators_b,
                                        news_count=None,
                                        fg={"value":"50", "value_classification":"Neutral"},
                                        generated_at=datetime.datetime.now().isoformat(timespec="seconds"),
                                    )
                                except Exception as _e:
                                    print(f"❌ Sheets log (batch) failed: {_e}")
                                st.caption(f"✅ บันทึกลงระบบสำเร็จเมื่อ {datetime.datetime.now().strftime('%H:%M')} น. (Reflection Mode)")
                                
                                # --- [NEW CODE] แทรกตรงนี้เพื่อส่งเข้า Discord ---
                                c_webhook = st.secrets.get("general", {}).get("crypto_webhook", "")
                                if c_webhook:
                                    from utils import send_crypto_report_to_discord
                                    send_crypto_report_to_discord(c_webhook, c_symbol, last_p, res_batch)
                                # -----------------------------------------------
                            else:
                                st.error("AI ไม่พร้อมใช้งาน")
                
                progress_bar.progress((idx + 1) / len(coin_list))
                time.sleep(0.5) 
            
            status_text.success("✅ วิเคราะห์และบันทึกข้อมูลครบทั้ง 8 เหรียญแล้วครับท่านเดียร์! (ใช้ระบบ 3-Step Self-Reflection)")

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
                valid_imgs = [convert_drive_link(img) for img in post['images'] if isinstance(img, str) and img.startswith("http")]
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
                                    if c['image'].startswith("http"): st.image(convert_drive_link(c['image']), width=200)
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

# =========================================================
# AUTO CHECK BACKTEST (Lazy Trigger at 21:00+)
# =========================================================
now_th = datetime.datetime.now()
if now_th.hour >= 21:  # เทศเวลา 21:00 น.
    if 'auto_checked' not in st.session_state:
        pending = dm.get_pending_predictions()
        if pending:
            wh_url = st.secrets.get("general", {}).get("crypto_webhook", "")
            if wh_url:
                try:
                    res = pe.check_accuracy_and_broadcast(wh_url)
                    st.toast("✅ ระบบทำการสรุปผล Daily Recap อัตโนมัติแล้ว!", icon="⚖️")
                except Exception as e:
                    print(f"Auto Check Error: {e}")
        st.session_state['auto_checked'] = True

st.markdown("<br><center><small style='color:#A370F7'>Small Group by Dearluxion © 2025</small></center>", unsafe_allow_html=True)