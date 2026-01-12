import re
import requests
import streamlit as st

# --- ฟังก์ชันแปลงลิงก์ Google Drive (รูป) ---
def convert_drive_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link:
            return "ERROR: นี่คือลิงก์โฟลเดอร์ครับ! ใช้ได้แค่ลิงก์ไฟล์ (คลิกขวาที่รูป > Share > Copy Link)"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match:
            file_id = match.group(1)
            # สูตรเจาะระบบดึงรูป (lh3)
            return f'https://lh3.googleusercontent.com/d/{file_id}'
    return link 

# --- ฟังก์ชันแปลงลิงก์ Google Drive (วิดีโอ) ---
def convert_drive_video_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link:
            return "ERROR: ลิงก์โฟลเดอร์ใช้ไม่ได้ครับ ต้องเป็นลิงก์ไฟล์วิดีโอ"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match:
            file_id = match.group(1)
            # แปลงเป็นลิงก์ Preview เพื่อใช้กับ Iframe
            return f'https://drive.google.com/file/d/{file_id}/preview'
    return link

# --- ฟังก์ชันแปลงข้อความ URL ให้เป็นลิงก์กดได้ ---
def make_clickable(text):
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank" style="color:#A370F7; text-decoration:underline; font-weight:bold;">\1</a>', text)

# --- ฟังก์ชันส่งโพสต์เข้า Discord ---
def send_post_to_discord(post):
    try:
        # ดึง Webhook จาก Secrets
        webhook_url = st.secrets["general"]["discord_webhook"]
    except:
        print("Webhook URL not found in secrets")
        return
    
    # ดึงรูปภาพแรกมาโชว์ (ถ้ามี)
    image_url = ""
    if post.get('images'):
        valid_imgs = [img for img in post['images'] if img.startswith("http")]
        if valid_imgs: image_url = valid_imgs[0]
    
    # สร้างข้อความ Embed สวยๆ
    embed_data = {
        "username": "Myla Post Update 📢",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "embeds": [{
            "title": f"✨ มีโพสต์ใหม่จากบอส! ({post['date']})",
            "description": post['content'],
            "color": int(post.get('color', '#A370F7').replace("#", ""), 16),
            "footer": {"text": f"ID: {post['id']}"}
        }]
    }
    
    # ถ้ามีรูป ใส่รูปใน Embed
    if image_url:
        embed_data['embeds'][0]['image'] = {"url": image_url}

    try:
        requests.post(webhook_url, json=embed_data)
    except Exception as e:
        print(f"Error sending to Discord: {e}")