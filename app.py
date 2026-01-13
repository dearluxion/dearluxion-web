import streamlit as st
import os
import datetime
import re
import time
import random
import base64
import google.generativeai as genai

# --- [IMPORTED MODULES] เรียกใช้โมดูลที่แยกไว้ ---
from styles import get_css 
from utils import convert_drive_link, convert_drive_video_link, make_clickable, send_post_to_discord, exchange_code_for_token, get_discord_user
import data_manager as dm
import sidebar_manager as sm

# --- 0. ตั้งค่า API KEY ---
GEMINI_API_KEY = "" # เอา Key ของเดียร์มาใส่ตรงนี้เหมือนเดิม

# Config Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') 
    ai_available = True
except:
    ai_available = False

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
        BOSS_ID = "420947252849410055"  # ID ของท่าน Dearluxion
        
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
search_query, selected_zone = sm.render_sidebar(model, ai_available)

# --- 3. Header & Profile ---
profile_data = dm.load_profile()
user_emoji = profile_data.get('emoji', '😎') 
user_status = profile_data.get('status', 'ยินดีต้อนรับสู่โลกของdearluxion ✨')
boss_avatar_url = profile_data.get('boss_avatar', '') # ดึงรูปลิงก์บอส

if not st.session_state['is_admin']:
    hour = datetime.datetime.now().hour
    greeting = "สวัสดีตอนเช้าค่ะ" if 5 <= hour < 12 else "สวัสดีตอนบ่ายค่ะ" if 12 <= hour < 18 else "สวัสดีตอนค่ำค่ะ"
    st.info(f"🧚‍♀️ **ไมล่า:** {greeting} พี่จ๋า~ กดลูกศร **มุมซ้ายบน** ↖️ เพื่อเปิดเมนูคุยกับไมล่าได้นะคะ!")

top_col1, top_col2 = st.columns([8, 1])
with top_col1:
    col_p1, col_p2 = st.columns([1.5, 6])
    with col_p1:
        # [ใหม่] เช็คว่าถ้ามีรูปบอส ให้โชว์รูป ถ้าไม่มีให้โชว์ Emoji
        if boss_avatar_url:
            real_avatar = convert_drive_link(boss_avatar_url)
            st.markdown(f"""
                <div style="width:100px; height:100px; border-radius:50%; overflow:hidden; border: 3px solid #A370F7; box-shadow: 0 0 15px rgba(163, 112, 247, 0.5); margin: 0 auto;">
                    <img src="{real_avatar}" style="width:100%; height:100%; object-fit: cover;">
                </div>
            """, unsafe_allow_html=True)
        else:
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
    tab_post, tab_profile, tab_inbox = st.tabs(["📝 เขียน / ขายของ", "👤 แก้ไขโปรไฟล์", "📬 อ่านจดหมายลับ"])
    
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

            st.markdown("---")
            st.markdown("#### 🎭 เลือกผู้โพสต์ (Identity)")
            # [ใหม่] ระบบสลับร่าง
            post_as = st.radio("โพสต์ในนาม:", ["👤 บอส (Dearluxion)", "🧚‍♀️ ไมล่า (Myla)"], horizontal=True)
            
            myla_mood_select = "ปกติ"
            if "ไมล่า" in post_as:
                myla_mood_select = st.radio("อารมณ์ไมล่า:", ["ปกติ (ร่าเริง)", "เศร้า (ดราม่า)"], horizontal=True)
                if myla_mood_select == "ปกติ (ร่าเริง)":
                    st.info(f"Using Image: {profile_data.get('myla_normal', 'ยังไม่ใส่รูปในโปรไฟล์')}")
                else:
                    st.warning(f"Using Image: {profile_data.get('myla_sad', 'ยังไม่ใส่รูปในโปรไฟล์')}")

        if st.button("🚀 โพสต์เลย", use_container_width=True):
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
                # [ใหม่] Logic กำหนดชื่อและรูปคนโพสต์
                final_author_name = profile_data.get('name', 'Dearluxion')
                final_author_avatar = convert_drive_link(profile_data.get('boss_avatar', ''))
                is_bot_post = False

                if "ไมล่า" in post_as:
                    final_author_name = "🧚‍♀️ Myla (AI)"
                    is_bot_post = True
                    raw_myla_img = profile_data.get('myla_normal', '')
                    if "เศร้า" in myla_mood_select:
                        raw_myla_img = profile_data.get('myla_sad', '')
                    final_author_avatar = convert_drive_link(raw_myla_img)

                new_post = {
                    "id": str(datetime.datetime.now().timestamp()),
                    "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "author_name": final_author_name,     # เพิ่ม key นี้
                    "author_avatar": final_author_avatar, # เพิ่ม key นี้
                    "is_bot": is_bot_post,                # เพิ่ม key นี้
                    "content": new_desc,
                    "images": final_img_links,
                    "video": final_vid_links,
                    "color": post_color,
                    "price": price,
                    "likes": 0,
                    "reactions": {'😻': 0, '🙀': 0, '😿': 0, '😾': 0, '🧠': 0},
                    "comments": []
                }
                
                # Logic AI Comment (ถ้าไมล่าโพสต์เอง ไม่ต้องเม้นตัวเอง)
                if not is_bot_post and ai_available:
                    try:
                        prompt = f"คุณคือ 'ไมล่า' (Myla) AI ผู้ช่วยสาวน้อยน่ารักประจำเว็บไซต์ Small Group ของบอส 'Dearluxion' บอสเพิ่งโพสต์ข้อความว่า: \"{new_desc}\" หน้าที่ของคุณ: คอมเมนต์ตอบกลับโพสต์นี้ของบอส (สั้นๆ น่ารัก กวนนิดๆ)"
                        response = model.generate_content(prompt)
                        myla_reply = response.text.strip()
                        new_post['comments'].append({"user": "🧚‍♀️ Myla (AI)", "text": myla_reply, "is_admin": False, "image": None})
                    except: pass
                
                current = dm.load_data()
                current.append(new_post)
                dm.save_data(current)
                
                try:
                    send_post_to_discord(new_post)
                    st.toast("ส่งเข้า Discord เรียบร้อย!", icon="📢")
                except: pass

                st.success("เรียบร้อย! โพสต์เสร็จสิ้น")
                st.session_state['num_img_links'] = 1
                st.session_state['num_vid_links'] = 1
                time.sleep(1); st.rerun()
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
        st.markdown("### 🧚‍♀️ จัดการร่างอวตาร (Identity)")
        st.info("💡 **Tips:** ใส่ลิงก์ Google Drive ของรูปภาพได้เลย (ตั้งค่า Share เป็น 'Everyone with the link' ด้วยนะ)")

        with st.form("pf_form"):
            st.markdown("#### 👤 ข้อมูลบอส (Dearluxion)")
            p_name = st.text_input("ชื่อที่แสดง", value=profile_data.get('name', 'Dearluxion'))
            # [ใหม่] ช่องใส่รูปบอส
            p_avatar = st.text_input("รูปโปรไฟล์บอส (Link)", value=profile_data.get('boss_avatar', ''), placeholder="ลิงก์ Google Drive / เว็บ")
            p_emoji = st.text_input("อิโมจิ (ใช้กรณีไม่มีรูป)", value=profile_data.get('emoji', '😎'))
            p_status = st.text_input("Status", value=profile_data.get('status', 'ว่างงาน...'))
            p_bio = st.text_input("Bio", value=profile_data.get('bio', ''))
            
            st.markdown("---")
            st.markdown("#### 🧚‍♀️ ข้อมูลไมล่า (Myla AI)")
            # [ใหม่] ช่องใส่รูปไมล่า
            myla_norm = st.text_input("รูปไมล่า (ปกติ)", value=profile_data.get('myla_normal', ''), placeholder="ลิงก์รูปตอนร่าเริง")
            myla_sad = st.text_input("รูปไมล่า (เศร้า)", value=profile_data.get('myla_sad', ''), placeholder="ลิงก์รูปตอนเศร้า")
            
            st.markdown("---")
            st.markdown("#### 🔗 โซเชียล")
            p_discord = st.text_input("Discord URL", value=profile_data.get('discord',''))
            p_ig = st.text_input("IG URL", value=profile_data.get('ig',''))
            p_ex = st.text_area("ลิงก์อื่นๆ", value=profile_data.get('extras',''))

            if st.form_submit_button("บันทึกข้อมูลทั้งหมด"):
                profile_data.update({
                    "name": p_name, 
                    "boss_avatar": p_avatar,
                    "emoji": p_emoji, 
                    "status": p_status, 
                    "bio": p_bio, 
                    "myla_normal": myla_norm,
                    "myla_sad": myla_sad,
                    "discord": p_discord, 
                    "ig": p_ig, 
                    "extras": p_ex
                })
                dm.save_profile(profile_data)
                st.success("อัปเดตข้อมูลและรูปภาพเรียบร้อย!")
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

# --- 5. Feed Display ---
posts = dm.load_data()
filtered = posts
if st.session_state['show_shop']:
    st.markdown("## 🛒 ร้านค้า (Shop Zone)")
    with st.expander("🧚‍♀️ พี่จ๋า~ หาทางกลับไม่เจอเหรอคะ? (จิ้มไมล่าสิ!) 💖", expanded=True):
        st.markdown("""<div class="cute-guide">✨ ทางลัดพิเศษสำหรับพี่คนโปรดของไมล่า! 🌈</div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 กลับบ้านกับไมล่า!", use_container_width=True):
                st.session_state['show_shop'] = False
                st.balloons(); time.sleep(1); st.rerun()
        with c2: st.info("👈 กดปุ่มนี้ ไมล่าจะพาพี่กลับหน้าหลักเองค่ะ!")
    filtered = [p for p in filtered if p.get('price', 0) > 0 or "#ร้านค้า" in p['content']]
    if not filtered: st.warning("ยังไม่มีสินค้าวางขายจ้า")
else:
    if selected_zone != "🏠 รวมทุกโซน": filtered = [p for p in filtered if selected_zone in p['content']]
    if search_query: filtered = [p for p in filtered if search_query.lower() in p['content'].lower()]

if filtered:
    for post in reversed(filtered):
        accent = post.get('color', '#A370F7')
        if 'reactions' not in post: post['reactions'] = {'😻': post.get('likes', 0), '🙀': 0, '😿': 0, '😾': 0, '🧠': 0}
        for e in ['😻', '🙀', '😿', '😾', '🧠']: 
            if e not in post['reactions']: post['reactions'][e] = 0

        # [ใหม่] ดึงข้อมูลผู้โพสต์จากโพสต์นั้นๆ (ถ้าเป็นโพสต์เก่าไม่มีข้อมูล ให้ใช้ข้อมูลบอสปัจจุบัน)
        p_name = post.get('author_name', profile_data.get('name', 'Dearluxion'))
        p_avatar = post.get('author_avatar', '')
        
        # ถ้าไม่มี avatar ในโพสต์ (โพสต์เก่า) ให้ลองไปดึงจาก profile บอส
        if not p_avatar and p_name == profile_data.get('name', 'Dearluxion'):
             p_avatar = convert_drive_link(profile_data.get('boss_avatar', ''))

        with st.container():
            col_head, col_del = st.columns([0.85, 0.15])
            with col_head:
                # [ใหม่] Logic สร้าง HTML รูปโปรไฟล์ (Image vs Emoji)
                avatar_html = ""
                if p_avatar:
                    avatar_html = f"""
                    <div style="width:50px; height:50px; border-radius:50%; overflow:hidden; border: 2px solid {accent}; flex-shrink: 0;">
                        <img src="{p_avatar}" style="width:100%; height:100%; object-fit: cover;">
                    </div>
                    """
                else:
                    avatar_html = f"""<div style="font-size:40px; line-height:1; filter: drop-shadow(0 0 5px {accent});">{user_emoji}</div>"""

                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
                    {avatar_html}
                    <div style="line-height:1.2;">
                        <div style="font-size:18px; font-weight:bold; color:#E6EDF3;">
                            {p_name} 
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
    if not st.session_state['show_shop']: st.info("ยังไม่มีโพสต์ครับ")

st.markdown("<br><center><small style='color:#A370F7'>Small Group by Dearluxion © 2025</small></center>", unsafe_allow_html=True)