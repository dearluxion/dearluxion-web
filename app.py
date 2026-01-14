import streamlit as st
import os
import datetime
import time
import random
import google.generativeai as genai

# --- IMPORT MODULES ---
from styles import get_css 
from utils import convert_drive_link, convert_drive_video_link, make_clickable, send_post_to_discord, exchange_code_for_token, get_discord_user
import data_manager as dm
import sidebar_manager as sm

# --- CONFIG ---
st.set_page_config(page_title="Small Group", page_icon="🍸", layout="centered")
st.markdown(get_css(), unsafe_allow_html=True)

# AI Setup
GEMINI_API_KEY = "" # ใส่ Key เดิมของท่านตรงนี้
ai_available = False
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        ai_available = True
except: pass

# --- SESSION STATE INIT ---
defaults = {
    'liked_posts': [], 'user_reactions': {}, 'last_comment_time': 0,
    'feed_tokens': 5, 'last_token_regen': time.time(),
    'bar_tokens': 5, 'last_bar_regen': time.time(),
    'is_admin': False, 'discord_user': None, 'show_shop': False
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- TOKEN REGEN (Passive Logic) ---
now = time.time()
if now - st.session_state['last_token_regen'] >= 60:
    add = int((now - st.session_state['last_token_regen']) // 60)
    st.session_state['feed_tokens'] = min(5, st.session_state['feed_tokens'] + add)
    st.session_state['last_token_regen'] = now

# --- LOGIN LOGIC ---
if "code" in st.query_params:
    try:
        code = st.query_params["code"]
        sec = st.secrets["discord_oauth"]
        token = exchange_code_for_token(sec["client_id"], sec["client_secret"], code, sec["redirect_uri"])
        user = get_discord_user(token["access_token"])
        st.session_state['discord_user'] = user
        if str(user['id']) == "420947252849410055": st.session_state['is_admin'] = True
        st.toast(f"Welcome {user['username']}!")
        st.query_params.clear()
        time.sleep(0.5)
        st.rerun()
    except: st.error("Login Failed")

# --- UI RENDER ---
search_query, selected_zone = sm.render_sidebar(model if ai_available else None, ai_available)
profile = dm.load_profile()

# Header
c1, c2 = st.columns([8, 1])
with c1:
    st.markdown(f"### 🍸 {profile.get('name', 'Dearluxion')}")
    st.caption(profile.get('status', '...'))
with c2:
    if st.button("🛒"): st.session_state['show_shop'] = True; st.rerun()

# Billboard
if profile.get('billboard', {}).get('text'):
    st.info(f"📢 **ประกาศ:** {profile['billboard']['text']}")

# --- ADMIN PANEL ---
if st.session_state['is_admin']:
    with st.expander("📝 เขียนโพสต์ใหม่"):
        desc = st.text_area("แคปชั่น")
        img_link = st.text_input("รูปลิงก์ (Google Drive/Web)")
        if st.button("โพสต์"):
            if desc:
                new_post = {
                    "id": str(now), "date": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "content": desc, "images": [convert_drive_link(img_link)] if img_link else [],
                    "comments": []
                }
                data = dm.load_data()
                data.append(new_post)
                dm.save_data(data) # Async save
                send_post_to_discord(new_post) # Async send
                st.success("โพสต์แล้ว!")
                time.sleep(1); st.rerun()

# --- FEED ---
posts = dm.load_data()
if st.session_state['show_shop']:
    st.title("🛒 Shop Zone")
    if st.button("🏠 กลับหน้าหลัก"): st.session_state['show_shop'] = False; st.rerun()
    filtered = [p for p in posts if p.get('price', 0) > 0]
else:
    filtered = posts
    if search_query: filtered = [p for p in filtered if search_query.lower() in p['content'].lower()]

# Display Loop
for post in reversed(filtered):
    with st.container(border=True):
        st.markdown(f"**{profile.get('name', 'Boss')}** <span style='color:#888; font-size:12px'>{post['date']}</span>", unsafe_allow_html=True)
        
        # Images
        if post.get('images'):
            st.image(post['images'][0], use_container_width=True)
            
        # Content
        st.markdown(make_clickable(post['content']), unsafe_allow_html=True)
        
        # Reactions
        cols = st.columns(6)
        emojis = ['😻', '🙀', '😿', '😾', '🧠']
        reactions = post.get('reactions', {})
        
        for i, emo in enumerate(emojis):
            with cols[i]:
                count = reactions.get(emo, 0)
                if st.button(f"{emo} {count}", key=f"r_{post['id']}_{i}"):
                    # Update Memory Logic
                    data = dm.load_data()
                    for p in data:
                        if p['id'] == post['id']:
                            p['reactions'] = p.get('reactions', {})
                            p['reactions'][emo] = p['reactions'].get(emo, 0) + 1
                            break
                    dm.save_data(data) # Async Save
                    st.rerun()
        
        # Comments
        with st.expander(f"💬 ความคิดเห็น ({len(post.get('comments', []))})"):
            for c in post.get('comments', []):
                st.markdown(f"<small><b>{c['user']}:</b> {c['text']}</small>", unsafe_allow_html=True)
            
            if st.session_state.get('discord_user') or st.session_state['is_admin']:
                with st.form(key=f"c_{post['id']}"):
                    txt = st.text_input("เม้นเลย...", label_visibility="collapsed")
                    if st.form_submit_button("ส่ง"):
                        if txt:
                            user_name = st.session_state['discord_user']['username'] if st.session_state['discord_user'] else "Admin"
                            data = dm.load_data()
                            for p in data:
                                if p['id'] == post['id']:
                                    p['comments'].append({"user": user_name, "text": txt})
                                    break
                            dm.save_data(data)
                            st.rerun()
            else:
                st.caption("🔒 Login Discord เพื่อคอมเมนต์")

st.markdown("<br><center><small style='color:#555'>Small Group by Dearluxion</small></center>", unsafe_allow_html=True)