import re
import requests
import streamlit as st
import urllib.parse
import datetime
import json

# --- ฟังก์ชันแปลงลิงก์ Google Drive (รูป) ---
# [UPDATE] ใช้สำหรับแสดงผลบนเว็บ (ชัดสุด)
def convert_drive_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link:
            return "ERROR: นี่คือลิงก์โฟลเดอร์ครับ! ใช้ได้แค่ลิงก์ไฟล์ (คลิกขวาที่รูป > Share > Copy Link)"
        
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match:
            file_id = match.group(1)
            # สูตรใหม่: ใช้ thumbnail endpoint + sz=s4000 
            return f'https://drive.google.com/thumbnail?id={file_id}&sz=s4000'
            
    return link 

# --- ฟังก์ชันแปลงลิงก์ Google Drive (วิดีโอ) ---
def convert_drive_video_link(link):
    if "drive.google.com" in link:
        if "/folders/" in link:
            return "ERROR: ลิงก์โฟลเดอร์ใช้ไม่ได้ครับ ต้องเป็นลิงก์ไฟล์วิดีโอ"
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
        if match:
            file_id = match.group(1)
            # แปลงเป็นลิงก์ Preview เพื่อใช้กับ Iframe บนหน้าเว็บ
            return f'https://drive.google.com/file/d/{file_id}/preview'
    return link

# --- ฟังก์ชันแปลงข้อความ URL ให้เป็นลิงก์กดได้ ---
def make_clickable(text):
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank" style="color:#A370F7; text-decoration:underline; font-weight:bold;">\1</a>', text)

# --- [NEW] Helper: แปลงลิงก์ Drive เป็นแบบที่ Discord ชอบ (เพื่อให้ GIF ขยับ) ---
def get_discord_friendly_image(url):
    # ถ้าเป็นลิงก์ thumbnail ที่เราแปลงมาแล้ว ให้ดึง ID ออกมาทำเป็น lh3 link
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        # lh3 link รองรับ GIF บน Discord ได้ดีกว่า thumbnail?id=...
        return f"https://lh3.googleusercontent.com/d/{file_id}"
    return url

# --- ฟังก์ชันส่งโพสต์เข้า Discord (Webhook ห้องรวม) ---
def send_post_to_discord(post):
    try:
        # ดึง Webhook จาก Secrets
        webhook_url = st.secrets["general"]["discord_webhook"]
    except:
        print("Webhook URL not found in secrets")
        return
    
    # 1. จัดการรูปภาพ (แปลงเป็นลิงก์ที่ Discord อ่านง่าย + GIF ขยับ)
    image_url = ""
    if post.get('images'):
        valid_imgs = [img for img in post['images'] if img.startswith("http")]
        if valid_imgs: 
            # แปลงลิงก์แรกให้เป็น lh3 เพื่อให้ GIF ขยับ
            image_url = get_discord_friendly_image(valid_imgs[0])
    
    # 2. จัดการวิดีโอ (สำคัญ: Drive Video เล่นใน Embed ไม่ได้ ต้องแปะลิงก์ให้กด)
    video_content = ""
    if post.get('video'):
        video_links = []
        for v in post['video']:
            # ถ้าเป็น YouTube
            if "youtu" in v:
                video_links.append(f"🎥 [คลิกเพื่อดู YouTube]({v})")
            # ถ้าเป็น Drive
            elif "drive.google.com" in v:
                # แปลงจาก preview เป็น view เพื่อให้กดแล้วเด้งไปดูง่ายๆ
                view_link = v.replace("/preview", "/view")
                video_links.append(f"🎬 [คลิกเพื่อดูคลิปวิดีโอ (Drive)]({view_link})")
            else:
                 video_links.append(f"📹 [คลิกเพื่อดูวิดีโอ]({v})")
        
        if video_links:
            video_content = "\n\n" + "\n".join(video_links)

    # รวมเนื้อหาโพสต์ + ลิงก์วิดีโอ
    final_description = post['content'] + video_content
    
    # สร้างข้อความ Embed สวยๆ
    embed_data = {
        "username": "Myla Post Update 📢",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "embeds": [{
            "title": f"✨ มีโพสต์ใหม่จากบอส! ({post['date']})",
            "description": final_description, # ใส่ลิงก์วิดีโอไปในนี้ด้วย
            "color": int(post.get('color', '#A370F7').replace("#", ""), 16),
            "footer": {"text": f"ID: {post['id']}"}
        }]
    }
    
    # ถ้ามีรูป ใส่รูปใน Embed
    if image_url:
        embed_data['embeds'][0]['image'] = {"url": image_url}

    try:
        # ส่ง Webhook หลัก (Embed)
        requests.post(webhook_url, json=embed_data)
        
        # [EXTRA] กรณีเป็น YouTube ให้ส่งลิงก์เพียวๆ ไปอีกข้อความ เพื่อให้มันเด้งจอ Player ขึ้นมา
        if post.get('video'):
            for v in post['video']:
                if "youtu" in v:
                    requests.post(webhook_url, json={"content": f"📺 **YouTube Player:** {v}"})

    except Exception as e:
        print(f"Error sending to Discord: {e}")

# --- [ใหม่] ฟังก์ชันส่งจดหมายลับเข้า DM บอสโดยตรง (พร้อมระบบสายสืบ + รูป) ---
def send_secret_to_discord(text, sender_info="ไม่ระบุตัวตน (Guest)", avatar_url=None):
    # 1. พยายามดึง Token ของบอท
    try:
        bot_token = st.secrets["discord_bot"]["token"]
    except:
        print("Error: ไม่พบ [discord_bot] token ใน secrets")
        return

    # ID ของ Boss (Dearluxion)
    boss_id = "420947252849410055"

    # Header สำหรับคุยกับ API Discord
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    try:
        # ขั้นตอน A: สร้าง/ขอเลขห้องแชทส่วนตัว (DM Channel) กับบอส
        dm_payload = {"recipient_id": boss_id}
        dm_req = requests.post("https://discord.com/api/v10/users/@me/channels", json=dm_payload, headers=headers)
        
        if dm_req.status_code == 200:
            channel_id = dm_req.json()["id"] # ได้เลขห้องมาแล้ว

            # ขั้นตอน B: เตรียมหน้าตาข้อความ (Embed)
            embed = {
                "title": "💌 มีความลับถูกส่งมาถึงบอส! (Direct Message)",
                "description": f"```{text}```\n\n🕵️ **สายสืบรายงาน:**\nคนส่งคือ: `{sender_info}`", 
                "color": 16738740, # สีชมพู Hot Pink
                "footer": {"text": "ส่งมาจากหน้าเว็บ Small Group (Secret Box)"},
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # [อัปเกรด] ใส่รูปคนส่ง (ถ้ามี)
            if avatar_url:
                embed["thumbnail"] = {"url": avatar_url}

            embed_data = {"embeds": [embed]}
            
            # ขั้นตอน C: ส่งเข้าห้อง DM
            send_req = requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json=embed_data, headers=headers)
            
            if send_req.status_code != 200:
                print(f"Failed to send DM: {send_req.text}")
        else:
            print(f"Failed to open DM Channel: {dm_req.text}")

    except Exception as e:
        print(f"Error logic sending DM: {e}")

# --- Discord Login Functions ---

# 1. ฟังก์ชันสร้างลิงก์ปุ่มกด Login
def get_discord_login_url(client_id, redirect_uri):
    base_url = "https://discord.com/api/oauth2/authorize"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify"
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

# 2. ฟังก์ชันเอารหัส Code ไปแลกเป็นกุญแจเข้าบ้าน (Token)
def exchange_code_for_token(client_id, client_secret, code, redirect_uri):
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    r.raise_for_status()
    return r.json()

# 3. ฟังก์ชันดึงข้อมูลชื่อและรูปโปรไฟล์
def get_discord_user(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://discord.com/api/users/@me", headers=headers)
    r.raise_for_status()
    return r.json()

# --- [NEW] ฟังก์ชันส่งผลวิเคราะห์ Crypto God Mode เข้า Discord ---
def send_crypto_report_to_discord(webhook_url, symbol, price, analysis_text):
    """ส่งผลวิเคราะห์ Crypto God Mode ไปยัง Discord"""

    if not webhook_url:
        print("❌ No Crypto Webhook URL provided")
        return

    # ตัดข้อความถ้ามันยาวเกินลิมิต Discord (4096 chars)
    if len(analysis_text) > 4000:
        analysis_text = analysis_text[:3900] + "... (อ่านต่อในเว็บ)"

    # กำหนดสีตามเนื้อหา (ถ้า Bullish สีเขียว, Bearish สีแดง, อื่นๆ สีทอง)
    embed_color = 16766720 # สีทอง (Gold) ค่าเริ่มต้น
    if "BULLISH" in analysis_text or "น่าเก็บ" in analysis_text:
        embed_color = 5763719 # สีเขียว (Green)
    elif "BEARISH" in analysis_text or "เสี่ยง" in analysis_text:
        embed_color = 15548997 # สีแดง (Red)

    embed_data = {
        "username": "Crypto God Oracle 🔮",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/6001/6001368.png",
        "embeds": [{
            "title": f"💎 God Mode Analysis: {symbol.upper()}",
            "description": analysis_text,
            "color": embed_color,
            "fields": [
                {
                    "name": "💰 ราคาปัจจุบัน",
                    "value": f"฿{price:,.4f} THB",
                    "inline": True
                },
                {
                    "name": "🧠 วิเคราะห์โดย",
                    "value": "Gemini 2.5 (3-Step Reflection)",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Small Group Crypto War Room | {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
            }
        }]
    }

    try:
        requests.post(webhook_url, json=embed_data)
        print(f"✅ Sent {symbol} report to Discord")
    except Exception as e:
        print(f"❌ Failed to send crypto report: {e}")