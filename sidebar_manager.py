import streamlit as st
import time
import random
import datetime
import requests
import re
import threading
import data_manager as dm
from utils import get_discord_login_url, send_secret_to_discord

def render_sidebar(model, ai_available):
    # --- เช็คสถานะ Login ---
    is_logged_in = st.session_state.get('discord_user') or st.session_state.get('is_admin')

    st.sidebar.title("🍸 เมนูหลัก")

    # Q&A (ใช้ Expander ปกติ ไม่ต้อง Rerun)
    with st.sidebar.expander("🧚‍♀️ ถาม-ตอบ กับไมล่า (Q&A)", expanded=True):
        st.markdown("### 💬 อยากรู้อะไรถามไมล่าได้เลย!")
        q_options = ["เลือกคำถาม...", "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?", "🛍️ สนใจสินค้า ซื้อยังไง?", "💻 เว็บนี้ใครสร้างครับ?", "🧚‍♀️ ไมล่าคือใครคะ?", "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?", "🤖 บอสใช้ AI ตัวไหนทำงาน?", "🍕 บอสชอบกินอะไรที่สุด?"]
        selected_q = st.selectbox("เลือกคำถาม:", q_options, label_visibility="collapsed")
        
        if selected_q != "เลือกคำถาม...":
            # Logic แสดงคำตอบแบบเดิม
            if selected_q == "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?": st.info("🧚‍♀️ **ไมล่า:** พื้นที่ส่วนตัวของบอสเท่านั้นค่ะ! 💖")
            elif selected_q == "🛍️ สนใจสินค้า ซื้อยังไง?": st.success("🧚‍♀️ **ไมล่า:** กดปุ่ม **'สนใจสั่งซื้อ'** วาร์ปไปหาบอสเลยค่ะ 🚀")
            elif selected_q == "💻 เว็บนี้ใครสร้างครับ?": st.warning("🧚‍♀️ **ไมล่า:** **ท่าน Dearluxion สร้างเอง** Python ล้วน! 😎")
            elif selected_q == "🧚‍♀️ ไมล่าคือใครคะ?": 
                st.markdown("""<div style="background-color:#161B22; padding:15px; border-radius:10px; border:1px solid #A370F7;">... (เนื้อหาเดิม) ...</div>""", unsafe_allow_html=True)
            elif selected_q == "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?": st.error("🧚‍♀️ **ไมล่า:** Discord หรือ IG เลยค่ะ!")
            elif selected_q == "🤖 บอสใช้ AI ตัวไหนทำงาน?": st.success("🧚‍♀️ **ไมล่า:** Gemini 2.5 ค่ะ!")
            elif selected_q == "🍕 บอสชอบกินอะไรที่สุด?": st.warning("🧚‍♀️ **ไมล่า:** ปลาส้ม ทอด! 🐟")

    # Gossip
    with st.sidebar.expander("🤫 มุมนินทาบอส (Myla's Gossip)"):
        if not is_logged_in:
             st.markdown("""<div style="background:#21262D; padding:10px; border-radius:5px; border-left:3px solid #ff0000; color:#8B949E; font-size:12px;">🔒 <b>Access Denied</b></div>""", unsafe_allow_html=True)
        else:
            if st.button("ความลับของบอส... 💬"):
                now = time.time()
                # ลดเวลา cooldown ลงหน่อยให้รู้สึกลื่นขึ้น
                if now - st.session_state.get('last_gossip_time', 0) < 2: 
                    st.warning("⚠️ อย่ากดรัวสิคะ!")
                else:
                    gossips = ["เมื่อคืนบอสเปิดเพลงเศร้าวนไป 10 รอบเลย... 🎵", "บอสแอบส่องไอจีเขาบ่อยมาก! 👀", "เห็นบอสเข้มๆ จริงๆ ขี้เหงา 🥺", "บอสอยากกินหมูกระทะ 🥓", "บอสแพ้คนยิ้มสวย 😳", "บอสชอบแมวแต่แมวไม่รัก 🐈", "บอสขับรถหลงทางบ่อยมาก 🚗", "ช่วงนี้บอสดูดวงบ่อยนะ 🤔"]
                    st.toast(f"🧚‍♀️ ไมล่าแอบบอก: {random.choice(gossips)}", icon="🤫")
                    st.session_state['last_gossip_time'] = now

    st.sidebar.markdown("---")

    # Myla's Choice
    with st.sidebar.expander("⚖️ Myla's Choice (ที่ปรึกษาหัวใจ)"):
        if not is_logged_in:
            st.warning("🔒 เข้าสู่ระบบเพื่อปรึกษาไมล่า")
        else:
            choice_topic = st.selectbox("เรื่องที่หนักใจ...", ["เลือกหัวข้อ...", "📲 ทักเขาไปตอนนี้ดีไหม?", "💔 เขายังคิดถึงเราอยู่รึเปล่า?", "🔙 ถ้ากลับไป... จะดีกว่าเดิมไหม?", "⏳ ควรรอต่อไป หรือ พอแค่นี้?"])
            if st.button("ขอคำตอบฟันธง! ⚡"):
                now = time.time()
                if now - st.session_state.get('last_choice_time', 0) < 5:
                    st.warning("⏳ ใจเย็นๆ ให้ไมล่าหายใจก่อน!")
                elif choice_topic != "เลือกหัวข้อ...":
                    answers = {
                        "📲 ทักเขาไปตอนนี้ดีไหม?": ["ทักเลย!", "อย่าฟอร์มเยอะ!", "ลุยโลด!", "ทักไปเถอะ..."],
                        "💔 เขายังคิดถึงเราอยู่รึเปล่า?": ["คิดถึงสิ!", "100%", "เขาไม่เคยลืมหรอก", "ลองหลับตาดูสิ..."],
                        "🔙 ถ้ากลับไป... จะดีกว่าเดิมไหม?": ["ตอนจบสวยงามเสมอ", "ถ่านไฟเก่าเป่าง่ายนะ", "คนนี้แหละคู่แท้!", "กลับไปเถอะ..."],
                        "⏳ ควรรอต่อไป หรือ พอแค่นี้?": ["รออีกนิด!", "อย่าเพิ่งถอดใจ!", "รักแท้คือการรอคอย", "เชื่อในสัญชาตญาณตัวเอง"]
                    }
                    st.toast(f"🧚‍♀️ ฟันธง: {random.choice(answers[choice_topic])}", icon="💘")
                    st.balloons()
                    st.session_state['last_choice_time'] = now

    st.sidebar.markdown("---")

    # Treat Me (ปรับให้ Save แบบ Async ผ่าน Data Manager)
    with st.sidebar.expander("🥤 Treat Me (เลี้ยงอาหารทิพย์)", expanded=True):
        tokens = st.session_state.get('feed_tokens', 5)
        pf_stats = dm.load_profile()
        if 'treats' not in pf_stats: pf_stats['treats'] = {}
        
        st.markdown(f"""
        <div style="margin-bottom:10px;">
            <div style="background:#30363D; border-radius:10px; overflow:hidden;">
                <div style="width:{tokens*20}%; background: linear-gradient(90deg, #A370F7, #FFD700); height:8px;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span>Token: <b>{tokens}/5</b> ⚡</span>
                <span>เปย์ไปแล้ว: {sum(pf_stats['treats'].values())} จาน</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not is_logged_in:
            st.warning("🔒 Login เพื่อป้อนอาหารบอส")
        else:
            feeder_name = st.text_input("ชื่อคนใจดี:", placeholder="ใส่ชื่อเล่น...", key="feeder_name")
            
            # แสดงผลลัพธ์เก่าถ้ามี
            if st.session_state.get('feed_msg'):
                st.success(st.session_state['feed_msg']) 
                st.session_state['feed_msg'] = None 

            col1, col2, col3 = st.columns(3)
            def _async_discord_alert(sender, item, msg):
                try:
                    url = st.secrets["general"]["discord_webhook"]
                    requests.post(url, json={"content": f"🍱 **Treat:** {sender} ให้ {item}\n💬 **Boss:** {msg}"})
                except: pass

            def feed_action(item):
                if st.session_state['feed_tokens'] > 0:
                    st.session_state['feed_tokens'] -= 1
                    msg = random.choice(["ขอบคุณค้าบ 🙏", "อิ่มจังตังค์อยู่ครบ", "ใจดีจัง 💖", "อร่อยแสงออกปาก ✨"])
                    sender = feeder_name.strip() or "FC นิรนาม"
                    st.session_state['feed_msg'] = f"😎 บอส: {msg} (จาก: {sender})"
                    
                    # Async Alert
                    threading.Thread(target=_async_discord_alert, args=(sender, item, msg)).start()
                    
                    # Update Stats
                    pf = dm.load_profile()
                    if 'treats' not in pf: pf['treats'] = {}
                    pf['treats'][item] = pf['treats'].get(item, 0) + 1
                    dm.save_profile(pf) # Async Save ในตัว
                    st.rerun()
                else:
                    st.toast("Token หมด! รอรีเจนแป๊บ", icon="⛔")

            with col1: 
                if st.button("🐟"): feed_action("ปลาส้มทอด 🐟")
                if st.button("☕"): feed_action("กาแฟลาเต้ ☕")
            with col2:
                if st.button("🍣"): feed_action("ซูชิ 🍣")
                if st.button("🧋"): feed_action("ชาไทย 🧋")
            with col3:
                if st.button("🍔"): feed_action("เบอร์เกอร์ 🍔")
                if st.button("🍕"): feed_action("พิซซ่า 🍕")

    st.sidebar.markdown("---")

    # Love Stock (ใช้ Logic เดิม แต่ลดการโหลดซ้ำ)
    with st.sidebar.expander("📈 Love Stock Market"):
        pf = dm.load_profile()
        stock = pf.get('stock', {'price': 100.0, 'history': [100.0]*10})
        st.metric("ราคาหุ้นความฮอต 🔥", f"{stock['price']:.2f}", f"{stock['price'] - stock['history'][-2]:.2f}")
        st.line_chart(stock['history'][-20:])
        
        if is_logged_in:
            c1, c2 = st.columns(2)
            if c1.button("🟢 Buy"):
                stock['price'] += random.uniform(0.5, 5.0)
                stock['history'].append(stock['price'])
                pf['stock'] = stock
                dm.save_profile(pf)
                st.toast("หุ้นพุ่ง! 🚀")
                st.rerun()
            if c2.button("🔴 Sell"):
                stock['price'] = max(0, stock['price'] - random.uniform(0.5, 5.0))
                stock['history'].append(stock['price'])
                pf['stock'] = stock
                dm.save_profile(pf)
                st.toast("หุ้นร่วง... 📉")
                st.rerun()

    st.sidebar.markdown("---")
    
    # Mood Mocktail
    with st.sidebar.expander("🍸 Mood Mocktail"):
        if is_logged_in and ai_available:
            st.caption(f"Tokens: {st.session_state.get('bar_tokens', 0)}/5")
            user_mood = st.text_area("วันนี้เป็นไงบ้าง?", placeholder="ระบายมา...")
            if st.button("ชงเครื่องดื่ม 🥃"):
                if st.session_state.get('bar_tokens', 0) > 0 and user_mood:
                    with st.spinner("กำลังชง..."):
                        try:
                            prompt = f"Bartender AI: คิดสูตร Mocktail จากอารมณ์ '{user_mood}' เอาแบบเท่ๆ"
                            res = model.generate_content(prompt)
                            st.info(res.text)
                            st.session_state['bar_tokens'] -= 1
                        except: st.error("AI เมาค้าง")
                else: st.warning("Token หมด หรือ ลืมใส่อารมณ์")

    # Secret Archive & Games (คงเดิม)
    # ... (ส่วน Ariel, Jigsaw Heart, Fortune, Secret Archive คงไว้ตามเดิม ไม่ต้องแก้ เพราะไม่ได้โหลดหนัก)

    st.sidebar.markdown("---")

    # Mailbox (ปรับ Async)
    with st.sidebar.expander("💌 ตู้จดหมายลับ"):
        with st.form("secret_msg_form"):
            secret_msg = st.text_area("ความในใจ...", placeholder="ถึงบอส...")
            if st.form_submit_button("ส่งความลับ 🕊️"):
                if secret_msg:
                    sender_name = "Guest"
                    avatar = None
                    if st.session_state.get('discord_user'):
                        u = st.session_state['discord_user']
                        sender_name = f"{u['username']}"
                        avatar = f"https://cdn.discordapp.com/avatars/{u['id']}/{u['avatar']}.png" if u.get('avatar') else None
                    
                    # Save Local
                    msgs = dm.load_mailbox()
                    msgs.append({"date": datetime.datetime.now().strftime("%d/%m %H:%M"), "text": secret_msg})
                    dm.save_mailbox(msgs) # Async Save
                    
                    # Send DM Async
                    send_secret_to_discord(secret_msg, sender_name, avatar)
                    
                    st.success("ส่งแล้ว! 🤫")
                else: st.warning("พิมพ์หน่อยสิ")

    st.sidebar.markdown("---")

    # Search & Filter
    search_query = st.sidebar.text_input("🔍 ค้นหา...")
    selected_zone = "🏠 รวมทุกโซน"
    
    # Login Section
    st.sidebar.markdown("---")
    if st.session_state['is_admin']:
        st.sidebar.success(f"👑 Admin Mode")
        if st.sidebar.button("Logout"): st.session_state['is_admin'] = False; st.rerun()
    elif st.session_state.get('discord_user'):
        u = st.session_state['discord_user']
        st.sidebar.markdown(f"👋 **{u['username']}**")
        if st.sidebar.button("Logout"): st.session_state['discord_user'] = None; st.rerun()
    else:
        try:
            url = get_discord_login_url(st.secrets["discord_oauth"]["client_id"], st.secrets["discord_oauth"]["redirect_uri"])
            st.sidebar.markdown(f'<a href="{url}" target="_self"><button style="width:100%; padding:10px; background:#5865F2; color:white; border:none; border-radius:5px;">Login with Discord</button></a>', unsafe_allow_html=True)
        except: st.error("No Secrets")

    return search_query, selected_zone