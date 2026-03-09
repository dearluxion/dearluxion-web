import streamlit as st
import time
import random
import datetime
import requests
import re
import data_manager as dm
import ai_manager as ai
from utils import get_discord_login_url, send_secret_to_discord

def render_sidebar(ai_available, posts=None):
    is_logged_in = st.session_state.get('discord_user') or st.session_state.get('is_admin')

    st.sidebar.title("🍸 เมนูหลัก")

    # ==================== ปุ่มคริปโต ====================
    if st.session_state.get('show_crypto'):
        st.sidebar.info("📈 กำลังอยู่ในห้องวิเคราะห์คริปโต (God Mode)")
        if st.sidebar.button("🏠 กลับหน้าหลัก", key="back_from_crypto_top", use_container_width=True):
            st.session_state['show_crypto'] = False
            st.rerun()
    else:
        if st.sidebar.button("📈 วิเคราะห์คริปโตเจาะลึก (God Mode Beta)", 
                           type="primary", 
                           use_container_width=True):
            st.session_state['show_crypto'] = True
            st.session_state['show_code_zone'] = False
            st.session_state['show_shop'] = False
            st.rerun()

    # ==================== Q&A กับไมล่า ====================
    with st.sidebar.expander("🧚‍♀️ ถาม-ตอบ กับไมล่า (Q&A)", expanded=True):
        st.markdown("### 💬 อยากรู้อะไรถามไมล่าได้เลย!")
        q_options = [
            "เลือกคำถาม...", "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?", "🛍️ สนใจสินค้า ซื้อยังไง?",
            "💻 เว็บนี้ใครสร้างครับ?", "🧚‍♀️ ไมล่าคือใครคะ?", "📞 ติดต่อบอส Dearluxion ได้ที่ไหน?",
            "🤖 บอสใช้ AI ตัวไหนทำงาน?", "🍕 บอสชอบกินอะไรที่สุด?"
        ]
        selected_q = st.selectbox("เลือกคำถาม:", q_options, label_visibility="collapsed")
        
        if selected_q == "🤔 อยากโพสต์เรื่องราวบ้างต้องทำไง?":
            st.info("🧚‍♀️ **ไมล่า:** ไม่ได้น้า~ นี่เป็น **พื้นที่ส่วนตัวของบอส Dearluxion** เท่านั้นค่ะ! แต่พี่ๆ สามารถคอมเมนต์ หรือส่งข้อความลับมาคุยกับบอสได้นะคะ")
        elif selected_q != "เลือกคำถาม...":
            st.info(f"🧚‍♀️ **ไมล่า:** {ai.get_myla_answer(selected_q)}")

    st.sidebar.markdown("---")
    
    search_query = st.sidebar.text_input("🔍 ค้นหา...", placeholder="พิมพ์คำค้นหา")
    
    if posts is None:
        posts = dm.load_data()
    all_hashtags = set()
    if posts:
        for p in posts:
            tags = re.findall(r"#([\w\u0E00-\u0E7F]+)", p['content'])
            for t in tags: all_hashtags.add(f"#{t}")

    st.sidebar.markdown("### 📂 โซนของคุณ")
    
    if 'show_crypto' not in st.session_state: st.session_state['show_crypto'] = False
    if 'show_code_zone' not in st.session_state: st.session_state['show_code_zone'] = False
    if 'show_shop' not in st.session_state: st.session_state['show_shop'] = False

    selected_zone = "🏠 รวมทุกโซน"   # ← ค่าเริ่มต้นป้องกัน UnboundLocalError

    if st.session_state.get('show_shop'):
        st.sidebar.info("🛒 กำลังดูร้านค้า")
        if st.sidebar.button("🏠 กลับหน้าหลัก"):
            st.session_state['show_shop'] = False
            st.rerun()
    elif st.session_state.get('show_code_zone'):
        st.sidebar.info("💻 กำลังดู Code Portfolio")
        if st.sidebar.button("🏠 กลับหน้าหลัก", key="back_from_code"):
            st.session_state['show_code_zone'] = False
            st.rerun()
    else:
        selected_zone = st.sidebar.radio("หมวดหมู่:", ["🏠 รวมทุกโซน"] + sorted(list(all_hashtags)))
        
        if st.sidebar.button("💻 Code Showcase / Portfolio", help="แจกโค้ดฟรี + โดเนท"):
            st.session_state['show_code_zone'] = True
            st.session_state['show_crypto'] = False
            st.session_state['show_shop'] = False
            st.rerun()

    st.sidebar.markdown("---")
    
    profile_data = st.session_state.get('profile', dm.load_profile())
    st.sidebar.markdown("---")
    
    if st.session_state.get('is_admin'):
        st.sidebar.success(f"👑 Admin: {profile_data.get('name', 'Boss')}")
        if st.sidebar.button("Log out (Admin)"):
            st.session_state['is_admin'] = False
            st.rerun()
    elif st.session_state.get('discord_user'):
        user = st.session_state['discord_user']
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user['avatar'] else "https://cdn-icons-png.flaticon.com/512/847/847969.png"
        
        st.sidebar.markdown(f"""
        <div style="background:#2b2d31; padding:10px; border-radius:8px; display:flex; align-items:center; gap:10px; border:1px solid #5865F2;">
            <img src="{avatar_url}" style="width:35px; height:35px; border-radius:50%;">
            <div style="overflow:hidden;">
                <div style="font-weight:bold; font-size:14px; color:white;">{user['username']}</div>
                <div style="font-size:10px; color:#aaa;">Logged in with Discord</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.sidebar.button("ออกจากระบบ"):
            st.session_state['discord_user'] = None
            st.rerun()
    else:
        st.sidebar.info("🔒 เข้าสู่ระบบเพื่อคอมเมนต์")
        try:
            d_id = st.secrets["discord_oauth"]["client_id"]
            d_uri = st.secrets["discord_oauth"]["redirect_uri"]
            login_link = get_discord_login_url(d_id, d_uri)
            st.sidebar.markdown(f'''
            <a href="{login_link}" target="_blank" style="text-decoration:none;">
                <button style="background-color:#5865F2; color:white; border:none; padding:10px; border-radius:5px; width:100%; font-weight:bold; cursor:pointer;">
                    👾 Login with Discord (New Tab)
                </button>
            </a>
            ''', unsafe_allow_html=True)
        except:
            st.error("ยังไม่ได้ตั้งค่า Secrets")
            
    return search_query, selected_zone