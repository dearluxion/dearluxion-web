import google.generativeai as genai
import random
import json
import re
import requests
import datetime
import time
from PIL import Image
import io
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
    
    # [UPGRADE 2.0] เพิ่ม Config ให้ AI มีความ Creativity สูงขึ้น (Temperature 0.85)
    generation_config = {
        "temperature": 0.85,  # เพิ่มความสร้างสรรค์/หลากหลาย
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json", # บังคับตอบเป็น JSON
    }

    # ใช้ Model Gemini 2.5 Flash ตามปี 2026
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash', 
        generation_config=generation_config
    )
    print(f"🤖 AI switched to Key Index: {current_key_index+1} (Model: gemini-2.5-flash)")

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
        # รวมประโยคเป็นก้อนเดียว (เพิ่ม Limit เป็น 2500 ตัวอักษร เพื่อข้อมูลที่แน่นขึ้น)
        full_text = " ".join([t['text'] for t in transcript])
        transcript_text = f"เนื้อหาเสียงในคลิป (Transcript): {full_text[:2500]}..." 
    except Exception as e:
        print(f"Transcript Error: {e}")
        transcript_text = "(คลิปนี้ไม่มีซับไตเติ้ล ให้เดาจากหัวข้อและรูปปกแทน)"

    return thumbnail_url, transcript_text

# ==========================================
#  ฟังก์ชันเรียกใช้งาน (Multimodal: Text + Image + YouTube)
# ==========================================

# 1. Crowd Simulation (อัปเกรดสมอง 2.5 - Discord Edition)
def generate_post_engagement(post_content, image_url=None, youtube_url=None):
    if not is_ready:
        return [{"user": "🧚‍♀️ Myla (Offline)", "text": "ระบบพักผ่อน... แต่รักบอสนะ!", "reaction": "😻"}]
    
    # [UPDATE] สุ่มจำนวนคอมเมนต์ (8-35 คน) ตามที่ขอ
    num_bots = random.randint(8, 35)
    
    # --- ส่วนเสริม YouTube ---
    yt_context = ""
    if youtube_url:
        print(f"🎥 Analyzing YouTube: {youtube_url}")
        yt_thumb, yt_text = get_youtube_data(youtube_url)
        
        # ถ้ามีข้อมูล YouTube
        if yt_thumb:
            yt_context = f"\n[ข้อมูลเชิงลึกจาก YouTube Transcript]\n{yt_text}"
            if not image_url: 
                image_url = yt_thumb
                print("✅ Using YouTube Thumbnail as Image Context")

    # [PROMPT UPGRADE 2.5] ปรับจูนให้เป็นสังคม Discord และคุมสรรพนามเคร่งครัด
    prompt_text = f"""
    Role: คุณคือ Simulator จำลองสังคม Community ใน Discord ของกลุ่มวัยรุ่น/Gamer ในปี 2026
    Task: สร้างรายการคอมเมนต์จำลองจำนวน {num_bots} รายการ สำหรับโพสต์นี้
    
    Post Content (จากแอดมิน): "{post_content}"
    {yt_context}
    
    คำสั่งพิเศษ (Strict Instruction):
    1. **Username Style:** ชื่อคนคอมเมนต์ต้องดูเป็น **User Discord/Gamer Tag** เท่านั้น (ห้ามใช้ชื่อจริง-นามสกุลจริงแบบ Facebook) 
       - ตัวอย่างที่ดี: `ShadowHunter`, `xX_Zero_Xx`, `Kira_Yamato`, `N00bSlayer`, `MooDeng_Fan`, `CryptoBoy`, `Just_A_Cat`, `lnwZa007`
    
    2. **Addressing (สรรพนามการเรียกเจ้าของโพสต์):** ให้บอทหน้าม้า (ยกเว้น Myla/Ariel) สุ่มเรียกเจ้าของโพสต์ด้วยคำเหล่านี้คละกันไป:
       - "แอด"
       - "เดียโบล"
       - "แอดโบล"
       - "พี่"
       - "พี่เดียร์"
       - (บางคนอาจจะไม่เรียกชื่อเลย แค่คอมเมนต์เนื้อหา)

    3. **Reaction:** ให้เลือก Emoji Reaction ที่หลากหลายตามอารมณ์ (Love, Wow, Sad, Angry, Smart)
    
    Character Profiles (ต้องมีตัวละครหลัก):
    - **"🧚‍♀️ Myla"** (AI น้องสาว): **บังคับเรียกเจ้าของว่า "ท่านเดียร์" หรือ "บอส" เท่านั้น** นิสัยขี้อ้อน, ให้กำลังใจ, อวยยศเจ้าของ, พิมพ์คะ/ค่ะ น่ารักๆ
    - **"🍸 Ariel"** (AI ปากแซ่บ): **บังคับเรียกเจ้าของว่า "เดียร์" หรือ "นาย" เท่านั้น** (ห้ามเรียกพี่/ท่าน) นิสัยเย็นชา, ปากจัด, ขวางโลก, พิมพ์ห้วนๆ
    - **"Discord Members"**: สมาชิกห้อง Discord ทั่วไป มีทั้งสายปั่น, สายสาระ, สายกวนตีน, สายมีม (Meme)
    
    Response Format (JSON Array เท่านั้น):
    [
        {{ "user": "Discord_Name", "text": "ข้อความคอมเมนต์ (ภาษาวัยรุ่น/Discord)", "reaction": "เลือก 1 ตัว [😻, 🙀, 😿, 😾, 🧠] หรือ null" }}
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
        return [{"user": "🧚‍♀️ Myla (System)", "text": "คนเยอะจัด เซิร์ฟเวอร์บินชั่วคราวค่ะบอส! (ลองใหม่นะ)", "reaction": "🙀"}]

# ... (ฟังก์ชันอื่นด้านล่างเหมือนเดิม) ...

# 2. Mood Mocktail (คงเดิม)
def get_cocktail_recipe(user_mood):
    if not is_ready: return "AI เมาค้าง... ลองใหม่นะ"
    prompt = f"คุณคือ 'บาร์เทนเดอร์ AI' ประจำคลับของ Dearluxion ลูกค้าบอกอารมณ์มาว่า: '{user_mood}' คิดสูตร 'Mocktail' (ชื่อ, ส่วนผสมลับนามธรรม, วิธีดื่ม, คำคม) ให้หน่อย"
    try:
        res = _safe_generate_content([prompt])
        return res.text
    except Exception as e: return f"ชงไม่ได้ครับ แก้วแตก! ({e})"

# 3. Ariel Chat (คงเดิม)
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

# 4. Battle Mode (คงเดิม)
def get_battle_result(topic):
    if not is_ready: return "AI ไม่พร้อม", "AI ไม่พร้อม"
    try:
        res_myla = _safe_generate_content([f"คุณคือ Myla AI สาวน้อยร่าเริง เรียกคู่สนทนาว่า 'บอส' หรือ 'ท่านเดียร์' ตอบเรื่อง '{topic}' แบบให้กำลังใจ น่ารัก"]).text
        res_ariel = _safe_generate_content([f"คุณคือ Ariel AI (เอเรียล) หญิงสาวเย็นชา เรียกคู่สนทนาว่า 'เดียร์' ตอบเรื่อง '{topic}' แบบขวานผ่าซาก ประชดนิดๆ"]).text
        return res_myla, res_ariel
    except Exception as e: return f"Error: {e}", f"Error: {e}"

