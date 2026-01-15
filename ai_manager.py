import google.generativeai as genai
import random
import json
import re
import requests
import datetime
import time
from PIL import Image
import io
# [NEW] Import ตัวดึงซับ YouTube
from youtube_transcript_api import YouTubeTranscriptApi

# --- Global Variables ---
api_keys = []        # รายการ Key ทั้งหมด
current_key_index = 0 # ตัวชี้ว่าตอนนี้ใช้ Key ไหนอยู่
model = None
is_ready = False

# [UPDATE] ตัวแปรสำหรับ Bot API
bot_token = None
target_user_id = None 

# [UPDATE] รับ bot_token และ boss_id แทน webhook
def init_ai(keys_list, discord_bot_token, boss_id):
    """
    เริ่มระบบ AI รองรับ Multi-Key และแจ้งเตือนผ่าน DM
    keys_list: list ของ API Key
    discord_bot_token: Token ของบอท (จาก Developer Portal)
    boss_id: Discord ID ของ Admin ที่จะให้ส่ง DM ไปหา
    """
    global api_keys, current_key_index, model, is_ready, bot_token, target_user_id
    
    try:
        # กรองเอาเฉพาะ Key ที่ไม่ว่าง
        api_keys = [k for k in keys_list if k and k.strip()]
        
        if not api_keys:
            print("❌ No API Keys provided")
            return False

        # เก็บค่า Token และ ID บอส
        bot_token = discord_bot_token
        target_user_id = boss_id

        current_key_index = 0 
        
        # Setup Model ด้วย Key แรก
        _setup_model()
        
        is_ready = True
        return True
    except Exception as e:
        print(f"AI Init Error: {e}")
        is_ready = False
        return False

def check_ready():
    return is_ready

def _setup_model():
    """ฟังก์ชันภายใน: ตั้งค่า Model ด้วย Key ปัจจุบัน"""
    global model, current_key_index
    current_key = api_keys[current_key_index]
    genai.configure(api_key=current_key)
    # ใช้ Model ที่รองรับรูปภาพ (Vision)
    model = genai.GenerativeModel('gemini-2.5-flash') # แนะนำรุ่น Flash เพราะไวและรองรับ Vision ดีมาก
    print(f"🤖 AI switched to Key Index: {current_key_index+1}")

# [UPDATE] ฟังก์ชันแจ้งเตือนแบบ DM (Bot API)
def _rotate_key_and_notify(error_msg):
    """ฟังก์ชันภายใน: สลับ Key อัตโนมัติ + แจ้ง Discord DM"""
    global current_key_index, is_ready
    
    dead_key_index = current_key_index
    
    # คำนวณ Index ถัดไป (วนลูป)
    next_index = (current_key_index + 1) % len(api_keys)
    
    current_key_index = next_index
    _setup_model() # Re-configure ทันที

    # --- ส่ง DM หาบอสผ่าน Bot API ---
    if bot_token and target_user_id:
        try:
            print("🚨 Sending DM Alert to Boss...")
            headers = {
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json"
            }
            
            # 1. เปิดห้องแชทส่วนตัว (DM Channel)
            dm_payload = {"recipient_id": target_user_id}
            dm_req = requests.post("https://discord.com/api/v10/users/@me/channels", json=dm_payload, headers=headers)
            
            if dm_req.status_code == 200:
                channel_id = dm_req.json()["id"]
                
                # 2. ส่งข้อความแจ้งเตือน
                embed_payload = {
                    "embeds": [{
                        "title": "⚠️ AI System Alert: Key Dead!",
                        "description": f"**Key ที่ตาย:** #{dead_key_index + 1}\n**สาเหตุ:** `{str(error_msg)}`\n**การแก้ไข:** 🔄 ระบบสลับไปใช้ **Key #{current_key_index + 1}** ให้แล้วค่ะ!",
                        "color": 16711680, # สีแดง
                        "timestamp": datetime.datetime.now().isoformat()
                    }]
                }
                requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json=embed_payload, headers=headers)
            else:
                print(f"Failed to open DM: {dm_req.text}")
                
        except Exception as e:
            print(f"Failed to send Bot DM alert: {e}")

def _safe_generate_content(inputs):
    """
    ฟังก์ชันวิเศษ: พยายาม Generate (รองรับทั้ง Text และ Image List)
    ถ้า Error จะสลับ Key แล้วลองใหม่
    """
    global is_ready
    if not is_ready: raise Exception("AI System not ready")

    max_retries = len(api_keys)
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(inputs)
            return response
        except Exception as e:
            error_str = str(e)
            # เช็คว่าเป็น Error เกี่ยวกับ Quota หรือไม่
            if "429" in error_str or "quota" in error_str.lower() or "exhausted" in error_str.lower():
                print(f"⚠️ Key #{current_key_index+1} Failed. Switching...")
                _rotate_key_and_notify(error_str)
                time.sleep(1) 
            else:
                raise e
    
    raise Exception("💀 All API Keys are dead/exhausted.")

# --- Helper: ล้าง JSON ---
def clean_json_text(text):
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()

# --- [NEW] Helper: ดึงข้อมูล YouTube ---
def get_youtube_data(url):
    """แกะ ID, ดึงรูปปก, และดึงซับไตเติ้ล"""
    video_id = None
    # Regex หา Video ID แบบครอบคลุม
    match = re.search(r'(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})', url)
    if match:
        video_id = match.group(1)
    
    if not video_id:
        return None, None

    # 1. สร้างลิงก์รูปปก (เอาไว้ให้ Vision Model ดู)
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    
    # 2. พยายามดึงซับไทย/อังกฤษ
    transcript_text = ""
    try:
        # พยายามดึงซับไทยก่อน ถ้าไม่มีเอาอังกฤษ
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['th', 'en'])
        # รวมประโยคเป็นก้อนเดียว (ตัดมาแค่ 1500 ตัวอักษรแรกก็พอ เดี๋ยว Token เต็ม)
        full_text = " ".join([t['text'] for t in transcript])
        transcript_text = f"เนื้อหาเสียงในคลิป (Transcript): {full_text[:1500]}..." 
    except Exception as e:
        print(f"Transcript Error: {e}")
        transcript_text = "(คลิปนี้ไม่มีซับไตเติ้ล ให้เดาจากหัวข้อและรูปปกแทน)"

    return thumbnail_url, transcript_text

# ==========================================
#  ฟังก์ชันเรียกใช้งาน (Multimodal: Text + Image + YouTube)
# ==========================================

# 1. Crowd Simulation
# [UPDATE] รับ youtube_url เพิ่มเข้ามา
def generate_post_engagement(post_content, image_url=None, youtube_url=None):
    if not is_ready:
        return [{"user": "🧚‍♀️ Myla (Offline)", "text": "ระบบพักผ่อน... แต่รักบอสนะ!", "reaction": "😻"}]
    
    num_bots = random.randint(5, 20)
    
    # --- ส่วนเสริม YouTube ---
    yt_context = ""
    if youtube_url:
        print(f"🎥 Analyzing YouTube: {youtube_url}")
        yt_thumb, yt_text = get_youtube_data(youtube_url)
        
        # ถ้ามีข้อมูล YouTube
        if yt_thumb:
            yt_context = f"\n[ข้อมูลเสริมจาก YouTube Link]\n{yt_text}"
            # ถ้าโพสต์ไม่มีรูปแนบ ให้ใช้รูปปกคลิปแทนเลย AI จะได้เห็นภาพ
            if not image_url: 
                image_url = yt_thumb
                print("✅ Using YouTube Thumbnail as Image Context")

    prompt_text = f"""
    Context: จำลองสังคมออนไลน์ในกลุ่ม Discord Community ของไทย
    Task: สร้างรายการ Interaction ของสมาชิกจำนวน {num_bots} คน ที่มาเห็นโพสต์นี้
    
    Post Content: "{post_content}"
    {yt_context}
    Image Context: (หากมีรูปภาพแนบมาด้วย ให้คอมเมนต์ถึงสิ่งที่เห็นในภาพด้วย)
    
    Requirements for Characters:
    
    1. **"🧚‍♀️ Myla"** (AI Assistant):
       - การเรียกเจ้าของโพสต์: "บอส" หรือ "ท่านเดียร์" เท่านั้น
       - นิสัย: ร่าเริง สดใส อวยยศเก่ง ใส่ใจ (ใช้ Emoji ได้เยอะๆ)
       - Context: ถ้าเป็นคลิปเพลง ให้พูดถึงแนวเพลงหรือเนื้อหา ถ้าเป็นคลิปข่าว ให้สรุปหรือตื่นเต้นตาม
       
    2. **"🍸 Ariel"** (AI Tsundere):
       - การเรียกเจ้าของโพสต์: "เดียร์" (ห้วนๆ สั้นๆ)
       - นิสัย: ปากไม่ตรงกับใจ เย็นชา ขวานผ่าซาก (ไม่ค่อยใช้อิโมจิ)
       
    3. **สมาชิกคนอื่นๆ (มนุษย์) อีก {num_bots - 2} คน**:
       - **Username (ชื่อ):** ห้ามใช้ชื่อไทยเชยๆ! ให้ใช้ชื่อสไตล์ Discord/Gamer เช่น `lnwza007`, `kik_jung`, `shadow_x`, `user99`, `ploy_sai`, `benz_gaming`, `nong_bamboo`, `zero_two`, `sky.blue`, `kapi_plara`, `nam_whan_za` (ผสมอังกฤษพิมพ์เล็ก/ตัวเลข/ขีดล่าง)
       - **การเรียกเจ้าของโพสต์:** สุ่มเลือกใช้คำว่า "พี่เดียร์", "แอดเดียร์", หรือ "โบ๋"
       - **สไตล์การพิมพ์ (สำคัญ):** - ต้องดูเป็น **มนุษย์** (Natural Human Text) พิมพ์เหมือนคนคุยกันในดิสคอร์ด
         - มีพิมพ์ห้วนๆ บ้าง, พิมพ์ยาวบ้าง, มีคำสแลง (ตึงๆ, เฟี้ยว, เข้มจัด, เอาเรื่อง, โบ๋จัด)
         - **Emoji:** ใส่บ้าง ไม่ใส่บ้าง (คนจริงไม่ใส่ Emoji ทุกประโยค)
         - **Context:** - ถ้าโพสต์มีรูปภาพ ให้วิจารณ์รูปภาพ หรือถามเกี่ยวกับสิ่งในรูป
           - ถ้าเป็น YouTube ให้พูดถึงเนื้อหาในคลิป (เพราะเรารู้ Transcript แล้ว)
           - ถ้าเป็นสินค้า ให้ถามราคา หรือสนใจ
           - ถ้าเป็นเรื่องเศร้า ให้พิมพ์ปลอบแบบวัยรุ่น หรือแซวว่า "โบ๋"
    
    Response Format (JSON Array only):
    [
        {{ "user": "Username", "text": "ข้อความคอมเมนต์", "reaction": "เลือก 1 ตัว [😻, 🙀, 😿, 😾, 🧠] หรือ null" }}
    ]
    """
    
    inputs = [prompt_text]

    if image_url:
        try:
            print(f"🖼️ Downloading image for AI: {image_url}")
            img_response = requests.get(image_url, timeout=10)
            img_data = Image.open(io.BytesIO(img_response.content))
            inputs.append(img_data)
            print("✅ Image loaded successfully!")
        except Exception as e:
            print(f"⚠️ Failed to load image: {e}")

    try:
        response = _safe_generate_content(inputs) 
        cleaned_text = clean_json_text(response.text)
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI Engagement Error: {e}")
        return [{"user": "🧚‍♀️ Myla (System)", "text": "ภาพสวยจน AI ตะลึง... ประมวลผลไม่ทันเลยค่ะ! (ลองกดใหม่นะ)", "reaction": "😻"}]

# 2. Mood Mocktail
def get_cocktail_recipe(user_mood):
    if not is_ready: return "AI เมาค้าง... ลองใหม่นะ"
    prompt = f"คุณคือ 'บาร์เทนเดอร์ AI' ประจำคลับของ Dearluxion ลูกค้าบอกอารมณ์มาว่า: '{user_mood}' คิดสูตร 'Mocktail' (ชื่อ, ส่วนผสมลับนามธรรม, วิธีดื่ม, คำคม) ให้หน่อย"
    try:
        res = _safe_generate_content([prompt])
        return res.text
    except Exception as e: return f"ชงไม่ได้ครับ แก้วแตก! ({e})"

# 3. Ariel Chat
def get_ariel_response(user_msg):
    if not is_ready: return "API ยังไม่พร้อม..."
    ariel_persona = """
    คุณคือ "เอเรียล" หญิงสาวบุคลิกเย็นชา ซับซ้อน มีอดีตที่บอบช้ำ               
    - **การเรียกคู่สนทนา:** เรียกว่า "เดียร์" คำเดียวห้วนๆ (หรือ "นาย" ถ้าโมโห) ห้ามเรียกพี่ เรียกท่าน
    - นิสัย: พูดน้อย ทรงพลัง ไม่ลงท้าย "คะ/ขา" เกลียดความโลกสวย
    - สไตล์: ปากไม่ตรงกับใจ (Tsundere) ประชดประชัน ชอบกินเงาะกระป๋อง
    """
    full_prompt = f"{ariel_persona}\n\nUser: {user_msg}\nAriel:"
    try:
        res = _safe_generate_content([full_prompt])
        return res.text.strip()
    except Exception as e: return f"เอเรียลไม่อยากคุยตอนนี้ ({e})"

# 4. Battle Mode
def get_battle_result(topic):
    if not is_ready: return "AI ไม่พร้อม", "AI ไม่พร้อม"
    try:
        res_myla = _safe_generate_content([f"คุณคือ Myla AI สาวน้อยร่าเริง เรียกคู่สนทนาว่า 'บอส' หรือ 'ท่านเดียร์' ตอบเรื่อง '{topic}' แบบให้กำลังใจ น่ารัก"]).text
        res_ariel = _safe_generate_content([f"คุณคือ Ariel AI (เอเรียล) หญิงสาวเย็นชา เรียกคู่สนทนาว่า 'เดียร์' ตอบเรื่อง '{topic}' แบบขวานผ่าซาก ประชดนิดๆ"]).text
        return res_myla, res_ariel
    except Exception as e: return f"Error: {e}", f"Error: {e}"