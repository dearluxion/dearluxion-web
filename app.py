import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("🕵️‍♂️ โค้ดตรวจสอบการเชื่อมต่อ Google Sheets")

st.write("---")
st.write("### 1. ตรวจสอบกุญแจใน Secrets")
if "gcp_service_account" in st.secrets:
    st.success("✅ เจอหัวข้อ [gcp_service_account] แล้ว!")
    
    # เช็คว่าก๊อปมาครบไหม
    key_data = st.secrets["gcp_service_account"]
    if "private_key" in key_data:
        if "-----BEGIN PRIVATE KEY-----" in key_data["private_key"]:
            st.success("✅ Private Key ดูถูกต้อง (มีขีดขึ้นต้นครบ)")
        else:
            st.error("❌ Private Key ผิดพลาด! (ต้องมี -----BEGIN PRIVATE KEY-----)")
    else:
        st.error("❌ ไม่เจอ private_key ในข้อมูล")
else:
    st.error("❌ ไม่เจอหัวข้อ [gcp_service_account] ใน Secrets! (ตรวจสอบการสะกดคำ)")

st.write("---")
st.write("### 2. ทดสอบไขเข้า Google Cloud")
try:
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    st.success("✅ ล็อกอิน Google Cloud ผ่าน!")
except Exception as e:
    st.error(f"❌ ล็อกอินไม่ผ่าน: {e}")
    st.stop()

st.write("---")
st.write("### 3. ทดสอบหาไฟล์ Google Sheets")
target_sheet = st.secrets.get("sheet_name", "streamlit_db")
st.info(f"กำลังหาไฟล์ชื่อ: {target_sheet}")

try:
    sh = client.open(target_sheet)
    st.success(f"🎉 เย้! เจอไฟล์แล้ว: {sh.title}")
    st.write(f"URL: {sh.url}")
    
    # ทดสอบเขียน
    st.write("...กำลังทดสอบเขียนข้อมูล...")
    ws = sh.sheet1
    ws.update_acell('Z1', 'Test Connection Success!')
    st.balloons()
    st.success("✅ เขียนข้อมูลสำเร็จ! (ลองไปดูใน Sheets ช่อง Z1 นะ)")
    
except Exception as e:
    st.error(f"❌ หาไฟล์ไม่เจอ หรือ เขียนไม่ได้: {e}")
    st.warning("""
    **วิธีแก้ที่เป็นไปได้:**
    1. ชื่อไฟล์ใน Google Sheets ต้องชื่อ `streamlit_db` เป๊ะๆ
    2. ต้องกด Share ไฟล์ Sheets ให้อีเมลบอท `client_email` (ดูใน Secrets)
    3. ต้องเลือกสิทธิ์เป็น **Editor** (ไม่ใช่ Viewer)
    """)