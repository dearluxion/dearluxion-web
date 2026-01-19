import streamlit as st
import os
import datetime
import re
import time
import random
import base64
import yfinance as yf
import plotly.graph_objects as go

# --- [IMPORTED MODULES] ---
from styles import get_css 
from utils import convert_drive_link, convert_drive_video_link, make_clickable, send_post_to_discord, exchange_code_for_token, get_discord_user
import data_manager as dm
import sidebar_manager as sm
import ai_manager as ai 

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

# --- 5. Feed Display & Crypto Zone (Main Logic) ---

if selected_zone == "📈 Crypto Zone":
    st.markdown("## 📈 Crypto AI Analyst (Myla & Ariel)")
    st.info("⚠️ **คำเตือน:** การลงทุนมีความเสี่ยง AI วิเคราะห์เพื่อความบันเทิงเท่านั้น (NFA)")

    # 1. เลือกเหรียญ
    col_coin, col_btn = st.columns([3, 1])
    with col_coin:
        coin_opt = st.selectbox("เลือกเหรียญที่จะส่อง:", 
            ["Bitcoin (BTC-USD)", "Shiba Inu (SHIB-USD)", "Ethereum (ETH-USD)", "Dogecoin (DOGE-USD)"])
        ticker_symbol = coin_opt.split("(")[1].replace(")", "")
    
    # 2. ดึงข้อมูล
    with st.spinner(f"กำลังดึงกราฟ {ticker_symbol} ..."):
        try:
            # ดึงข้อมูลย้อนหลัง 5 วัน กราฟรายชั่วโมง
            df = yf.download(ticker_symbol, period="5d", interval="1h", progress=False)
            
            # แก้ไขบั๊ก yfinance บางเวอร์ชันคืนค่าเป็น MultiIndex
            if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)

            if not df.empty:
                current_price = float(df['Close'].iloc[-1])
                # คำนวณ % เปลี่ยนแปลง 24 ชม. (24 แท่งเทียนย้อนหลัง)
                if len(df) > 24:
                    prev_price = float(df['Close'].iloc[-24])
                    change_24h = ((current_price - prev_price) / prev_price) * 100
                else:
                    change_24h = 0.0

                # 3. แสดงกราฟสวยๆ ด้วย Plotly
                fig = go.Figure(data=[go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'])])
                fig.update_layout(title=f"กราฟ {ticker_symbol} (5 วันล่าสุด)", 
                                  yaxis_title="ราคา (USD)", 
                                  template="plotly_dark",
                                  height=400)
                st.plotly_chart(fig, use_container_width=True)

                # แสดงราคาปัจจุบัน
                st.metric("ราคาปัจจุบัน", f"${current_price:,.6f}", f"{change_24h:.2f}%")

                # 4. ปุ่มให้ AI วิเคราะห์
                with col_btn:
                    st.write("") # ดันปุ่มลงมา
                    st.write("")
                    if st.button("🔮 ให้ AI วิเคราะห์", type="primary"):
                        # แปลงข้อมูลกราฟเป็น Text สั้นๆ ส่งให้ AI (เอา 5 จุดสุดท้าย)
                        trend_summary = str(df['Close'].tail(5).tolist())
                        
                        with st.spinner("Myla กำลังดูกราฟ... Ariel กำลังคำนวณ..."):
                            # เรียกฟังก์ชันใน ai_manager.py
                            analysis_result = ai.analyze_crypto(ticker_symbol, current_price, change_24h, trend_summary)
                            
                            st.markdown("---")
                            st.markdown("### 💬 ความเห็นจาก AI Persona")
                            st.markdown(analysis_result)
            else:
                st.error("ไม่สามารถดึงข้อมูลกราฟได้ (ตลาดอาจปิดหรือ API มีปัญหา)")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")

else:
    # --- 6. Feed Display (Original Feed Logic) ---
    posts = dm.load_data()
    filtered = posts
    
    # Filter Logic
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

    # Display Logic
    if filtered:
        for post in reversed(filtered):
            accent = post.get('color', '#A370F7')
            
            # Init Reactions
            if 'reactions' not in post: post['reactions'] = {'😻': post.get('likes', 0), '🙀': 0, '😿': 0, '😾': 0, '🧠': 0}
            for e in ['😻', '🙀', '😿', '😾', '🧠']: 
                if e not in post['reactions']: post['reactions'][e] = 0

            with st.container():
                st.markdown(f"""
                <div class="work-card-base" style="border-left: 5px solid {accent};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:12px; color:#8B949E; background:#21262D; padding:2px 8px; border-radius:10px;">📅 {post['date']}</span>
                        <span style="font-size:12px; color:{accent};">ID: {post['id']}</span>
                    </div>
                    <div style="margin-top:10px; font-size:16px; white-space: pre-wrap;">{make_clickable(post['content'])}</div>
                </div>
                """, unsafe_allow_html=True)

                # Show Price
                if post.get('price', 0) > 0:
                    st.markdown(f"""<div class="price-tag">💰 ราคา: {post['price']:,} บาท</div>""", unsafe_allow_html=True)
                    if st.button(f"🛒 สนใจสั่งซื้อ (Item {post['id']})", key=f"buy_{post['id']}"):
                        st.markdown(f"<meta http-equiv='refresh' content='0; url={profile_data.get('ig', '#')}'>", unsafe_allow_html=True)

                # Show Images
                if post.get('images'):
                    cols = st.columns(len(post['images']))
                    for idx, img_url in enumerate(post['images']):
                        with cols[idx]:
                            if "drive.google.com" in img_url and "thumbnail" in img_url:
                                st.markdown(f'<img src="{img_url}" style="width:100%; border-radius:10px;">', unsafe_allow_html=True)
                            else:
                                st.image(img_url, use_container_width=True)

                # Show Video
                if post.get('video'):
                    for v_link in post['video']:
                        if "youtube.com" in v_link or "youtu.be" in v_link:
                            st.video(v_link)
                        elif "drive.google.com" in v_link:
                            st.markdown(f'<iframe src="{v_link}" width="100%" height="300" frameborder="0" allow="autoplay"></iframe>', unsafe_allow_html=True)

                # Reactions Buttons
                c_react = st.columns([1,1,1,1,1, 3])
                emojis = ['😻', '🙀', '😿', '😾', '🧠']
                for idx, e in enumerate(emojis):
                    with c_react[idx]:
                        count = post['reactions'][e]
                        if st.button(f"{e} {count}", key=f"r_{post['id']}_{e}"):
                            # Update Logic
                            d = dm.load_data()
                            for x in d:
                                if x['id'] == post['id']:
                                    if 'reactions' not in x: x['reactions'] = post['reactions']
                                    x['reactions'][e] = x['reactions'].get(e, 0) + 1
                                    break
                            dm.save_data(d)
                            st.rerun()

                # Comments Section
                is_logged_in = st.session_state.get('discord_user') or st.session_state.get('is_admin')
                
                with st.expander(f"💬 ความคิดเห็น ({len(post['comments'])})"):
                    if not is_logged_in:
                        st.markdown(f"""
                        <div style="background: repeating-linear-gradient(45deg, #161B22, #161B22 10px, #0d1117 10px, #0d1117 20px); 
                                    padding: 20px; text-align: center; border-radius: 10px; border: 1px dashed #A370F7; color: #8B949E;">
                            <h3>🔒 ความลับของชาวแก๊ง!</h3>
                            <p>มีบทสนทนาลับๆ ซ่อนอยู่ {len(post['comments'])} ข้อความ...</p>
                            <small>(Login Discord เพื่อดูและคอมเมนต์)</small>
                        </div>""", unsafe_allow_html=True)
                    else:
                        if post['comments']:
                            for i, c in enumerate(post['comments']):
                                is_admin_comment = c.get('is_admin', False)
                                user_display = f"👑 {c['user']} (Owner)" if is_admin_comment else f"{c['user']}"
                                css_class = "admin-comment-box" if is_admin_comment else "comment-box"
                                
                                st.markdown(f"<div class='{css_class}'><b>{user_display}:</b> {c['text']}</div>", unsafe_allow_html=True)
                                if c.get('image'): st.image(c['image'], width=200)

                                if st.session_state['is_admin'] and st.button("ลบ", key=f"dc_{post['id']}_{i}"):
                                    d = dm.load_data()
                                    for x in d:
                                        if x['id'] == post['id']: x['comments'].pop(i); break
                                    dm.save_data(d); st.rerun()

                        # Comment Form
                        st.markdown("---")
                        admin_cmt_img = None
                        if st.session_state['is_admin']:
                            st.caption("👑 ตอบกลับในฐานะ Admin")
                            admin_cmt_img = st.text_input("ลิงก์รูป (Optional)", key=f"ci_{post['id']}")

                        with st.form(key=f"cf_{post['id']}"):
                            if st.session_state['is_admin']:
                                u_name = st.text_input("ชื่อคนตอบ", value="Dearluxion")
                            else:
                                u_name = st.session_state['discord_user']['username']
                                st.text_input("ชื่อผู้ใช้", value=u_name, disabled=True)

                            txt = st.text_input("ข้อความ", placeholder="แสดงความคิดเห็น...")
                            
                            if st.form_submit_button("ส่งคอมเมนต์"):
                                now = time.time()
                                if not st.session_state['is_admin'] and now - st.session_state['last_comment_time'] < 30:
                                    st.toast("ใจเย็นๆ พิมพ์เร็วไปแล้ว!", icon="⛔")
                                elif txt:
                                    final_img = convert_drive_link(admin_cmt_img) if admin_cmt_img else None
                                    d = dm.load_data()
                                    for x in d:
                                        if x['id'] == post['id']:
                                            x['comments'].append({"user": u_name, "text": txt, "is_admin": st.session_state['is_admin'], "image": final_img})
                                            break
                                    dm.save_data(d)
                                    if not st.session_state['is_admin']: st.session_state['last_comment_time'] = now
                                    st.rerun()
                st.markdown("---")

    else:
        if not st.session_state['show_shop']: st.info("ยังไม่มีโพสต์ครับ")

st.markdown("<br><center><small style='color:#A370F7'>Small Group by Dearluxion © 2026</small></center>", unsafe_allow_html=True)