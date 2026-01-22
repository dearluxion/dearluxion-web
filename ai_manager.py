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

# ตัวแปรสำหรับ Bot API
bot_token = None
target_user_id = None 

# --- Market Status Dictionary (Thai Version) ---
MARKET_STATUS_TH = {
    "BEARISH": {
        "icon": "🔴",
        "title": "ยังไม่ควรซื้อ",
        "short": "เสี่ยงขาลง",
        "description": "ราคายังมีแรงขาย และสัญญาณเทคนิคยังไม่สนับสนุนการเข้าซื้อ",
        "action": "รอให้ราคานิ่งหรือมีสัญญาณกลับตัวก่อน"
    },
    "NEUTRAL": {
        "icon": "🟡",
        "title": "ยังไม่ใช่ตอนนี้",
        "short": "รอดูทิศทาง",
        "description": "ตลาดยังไม่เลือกทาง ราคาแกว่งในกรอบ เข้าแล้วไม่คุ้มความเสี่ยง",
        "action": "รอจังหวะที่ได้เปรียบกว่านี้"
    },
    "BULLISH": {
        "icon": "🟢",
        "title": "เริ่มน่าสนใจ",
        "short": "แนวโน้มขาขึ้น",
        "description": "เริ่มมีแรงซื้อและสัญญาณบวกจากราคา",
        "action": "ทยอยสะสม พร้อมตั้ง Stop Loss"
    },
    "VERY_BULLISH": {
        "icon": "🔥",
        "title": "น่าเก็บมาก",
        "short": "จังหวะโกย (มีแผน)",
        "description": "สัญญาณซื้อชัด เงินไหลเข้า ความน่าจะเป็นเข้าทางฝั่งขึ้น",
        "action": "เข้าเป็นไม้ ห้าม All-in"
    },
    "TRAP": {
        "icon": "❌",
        "title": "อย่าเข้า",
        "short": "กับดักราคา",
        "description": "ราคาขึ้นแต่เงินไหลออก เสี่ยงโดนทุบหลังเข้า",
        "action": "ยืนดู ห้าม FOMO"
    }
}

def get_market_status_th(status_key: str):
    """
    รับค่า: BEARISH / NEUTRAL / BULLISH / VERY_BULLISH / TRAP
    คืนค่า: dict ภาษาไทยพร้อมใช้งาน
    """
    return MARKET_STATUS_TH.get(status_key.upper(), {
        "icon": "❓",
        "title": "ไม่ทราบสถานะ",
        "short": "-",
        "description": "ไม่มีข้อมูลสถานะตลาด",
        "action": "รอข้อมูลเพิ่มเติม"
    })

# --- 0. INIT AI FUNCTION (ส่วนที่เคยหายไป) ---
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
    
    generation_config = {
        "temperature": 0.85,  
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }

    # ใช้ Model Gemini 2.5 Flash ตามปี 2026
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash', 
        generation_config=generation_config
    )
    print(f"🤖 AI switched to Key Index: {current_key_index+1} (Model: gemini-2.5-flash)")

# ฟังก์ชันแจ้งเตือนแบบ DM (Bot API)
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
            if "429" in error_str or "quota" in error_str.lower() or "exhausted" in error_str.lower():
                print(f"⚠️ Key #{current_key_index+1} Failed. Switching...")
                _rotate_key_and_notify(error_str)
                time.sleep(1) 
            else:
                raise e
    
    raise Exception("💀 All API Keys are dead/exhausted.")

def clean_json_text(text):
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()

def get_youtube_data(url):
    """แกะ ID, ดึงรูปปก, และดึงซับไตเติ้ล"""
    video_id = None
    match = re.search(r'(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})', url)
    if match:
        video_id = match.group(1)
    
    if not video_id:
        return None, None

    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    transcript_text = ""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['th', 'en'])
        full_text = " ".join([t['text'] for t in transcript])
        transcript_text = f"เนื้อหาเสียงในคลิป (Transcript): {full_text[:2500]}..." 
    except Exception as e:
        print(f"Transcript Error: {e}")
        transcript_text = "(คลิปนี้ไม่มีซับไตเติ้ล ให้เดาจากหัวข้อและรูปปกแทน)"

    return thumbnail_url, transcript_text

# ==========================================
#  ฟังก์ชันเรียกใช้งานหลัก
# ==========================================

# 1. Crowd Simulation
def generate_post_engagement(post_content, image_url=None, youtube_url=None):
    if not is_ready:
        return [{"user": "🧚‍♀️ Myla (Offline)", "text": "ระบบพักผ่อน... แต่รักบอสนะ!", "reaction": "😻"}]
    
    num_bots = random.randint(8, 35)
    
    yt_context = ""
    if youtube_url:
        print(f"🎥 Analyzing YouTube: {youtube_url}")
        yt_thumb, yt_text = get_youtube_data(youtube_url)
        if yt_thumb:
            yt_context = f"\n[ข้อมูลเชิงลึกจาก YouTube Transcript]\n{yt_text}"
            if not image_url: 
                image_url = yt_thumb

    prompt_text = f"""
    Role: คุณคือ Simulator จำลองสังคม Community ใน Discord ของกลุ่มวัยรุ่น/Gamer ในปี 2026
    Task: สร้างรายการคอมเมนต์จำลองจำนวน {num_bots} รายการ สำหรับโพสต์นี้
    
    Post Content (จากแอดมิน): "{post_content}"
    {yt_context}
    
    คำสั่งพิเศษ:
    1. **Username:** ชื่อคนคอมเมนต์ต้องดูเป็น User Discord/Gamer Tag (ห้ามใช้ชื่อจริง-นามสกุลจริง)
    2. **Addressing:** เรียกเจ้าของโพสต์ว่า "แอด", "พี่เดียร์", "บอส", "เดียโบล" คละกันไป
    3. **Character:**
       - "🧚‍♀️ Myla": เรียก "ท่านเดียร์/บอส" นิสัยขี้อ้อน
       - "🍸 Ariel": เรียก "เดียร์/นาย" นิสัยเย็นชา ปากแซ่บ
       - "Members": สายปั่น, สายมีม, สายสาระ
    
    Response Format (JSON Array):
    [
        {{ "user": "Name", "text": "Comment", "reaction": "Emoji [😻, 🙀, 😿, 😾, 🧠] or null" }}
    ]
    """
    
    inputs = [prompt_text]
    if image_url:
        try:
            img_response = requests.get(image_url, timeout=10)
            img_data = Image.open(io.BytesIO(img_response.content))
            inputs.append(img_data)
        except Exception as e:
            print(f"⚠️ Failed to load image: {e}")

    try:
        response = _safe_generate_content(inputs) 
        cleaned_text = clean_json_text(response.text)
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI Engagement Error: {e}")
        return [{"user": "🧚‍♀️ Myla (System)", "text": "คนเยอะจัด เซิร์ฟเวอร์บินชั่วคราวค่ะบอส!", "reaction": "🙀"}]

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
    - เรียกว่า "เดียร์" คำเดียวห้วนๆ (หรือ "นาย") ห้ามเรียกพี่ เรียกท่าน
    - ปากไม่ตรงกับใจ (Tsundere) ประชดประชัน ชอบกินเงาะกระป๋อง
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

# 5. Crypto God Mode V3 (Simple "Pro Friend" Mode)
def analyze_crypto_god_mode(coin_name, current_price, indicators, news_text, fear_greed):
    if not is_ready: return "⚠️ ระบบ AI ยังไม่พร้อม (กรุณาใส่ API Key)"
    
    # ดึงค่า Indicators (เหมือนเดิม เพื่อความแม่นยำ)
    rsi = float(indicators.get('rsi', 50))
    stoch_k = float(indicators.get('stoch_k', 50))
    obv_status = str(indicators.get('obv_slope', 'N/A'))
    adx = float(indicators.get('adx', 20))
    atr = float(indicators.get('atr', 0))
    
    pivot_p = float(indicators.get('pivot_p', 0))
    pivot_s1 = float(indicators.get('pivot_s1', 0))
    pivot_r1 = float(indicators.get('pivot_r1', 0))
    
    # [NEW PROMPT V3.0] - เปลี่ยนจากผู้จัดการกองทุน เป็น "เพื่อนนักเทรดภาษาชาวบ้าน"
    prompt = f"""
    Role: คุณคือ "เพื่อนนักเทรดมือโปร" ที่คุยภาษาชาวบ้าน เข้าใจง่าย ไม่ใช้ศัพท์เทคนิคเยอะ
    Task: ให้คำแนะนำการเทรดเหรียญ {coin_name} สั้นๆ ง่ายๆ สำหรับคนทั่วไป
    
    [ข้อมูลราคาปัจจุบัน]
    ราคา: {current_price:,.2f} THB
    
    [ข้อมูลเชิงลึก (AI ประมวลผลเอง ไม่ต้องพูดศัพท์พวกนี้ออกมา)]
    - RSI: {rsi} (สูง=แพงไป/ระวังร่วง, ต่ำ=ถูก/น่าเก็บ)
    - เงินทุนไหลเข้า/ออก (OBV): {obv_status} (ถ้าเงินออก ห้ามแนะนำให้ซื้อสวน)
    - ความแรงของเทรนด์ (ADX): {adx}
    - แนวรับสำคัญ (ของถูก): {pivot_s1:,.2f} THB
    - แนวต้าน (จุดขายทำกำไร): {pivot_r1:,.2f} THB
    
    [คำสั่งการตอบ - ภาษาคนง่ายๆ]
    1. **สรุปสถานะ:** บอกเลยว่าตอนนี้ "น่าซื้อเก็บ", "รอก่อนยังไม่น่าเข้า", หรือ "หนีก่อนดอยแน่"
    2. **ถ้าแนะนำให้ซื้อ:** บอกเลยว่า "รอช้อนตอนราคาร่วงมาถึง {pivot_s1:,.2f} บาท จะสวยมาก"
    3. **ถ้าแนะนำให้รอ:** บอกเหตุผลบ้านๆ เช่น "ตอนนี้ราคามันขึ้นไปสูงเกินแล้ว เดี๋ยวก็ร่วง รอรับของถูกดีกว่า" หรือ "คนกำลังแห่ขาย อย่าเพิ่งเข้าไปรับมีด"
    4. **เป้าขาย:** ถ้าซื้อแล้ว กะว่ามันจะขึ้นไปถึงกี่บาท
    
    [รูปแบบการตอบ - MARKDOWN ภาษาไทย (Easy Mode)]
    
    ## 🐻 สรุปเหรียญ {coin_name} (ฉบับภาษาคน)
    **เวลา:** {datetime.datetime.now().strftime('%H:%M')} น.
    
    ### 🚦 **ตกลงเอาไงดี?:** [ใส่คำแนะนำสั้นๆ ตัวหนาๆ เช่น "รอก่อน อย่าเพิ่งห้าว", "ราคานี้เริ่มน่าเก็บแล้ว"]
    
    ### 📉 **แผนการเล่นง่ายๆ:**
    * **จุดรอช้อน (ที่น่าจะปลอดภัย):** แนะนำให้ตั้งรอแถวๆ **฿{pivot_s1:,.2f}** ครับ ราคานี้ถือว่าได้เปรียบ
    * **ถ้าได้อของแล้ว ไปขายตรงไหน?:** ถ้ามันเด้งขึ้น กะขายทำกำไรแถวๆ **฿{pivot_r1:,.2f}** หรือแบ่งขายกลางทางที่ **฿{pivot_p:,.2f}** ก็ได้ครับ
    * **จุดหนีตาย (Stop Loss):** ถ้าหลุด **฿{pivot_s1 - (atr * 1.5):,.2f}** ให้รีบคัททิ้งก่อนเจ็บหนักครับ
    
    ### 💬 **บ่นให้ฟัง (เหตุผล):**
    [อธิบายเหตุผลแบบเพื่อนคุยกัน 2-3 บรรทัด เช่น "ที่บอกให้รอก่อนเพราะตอนนี้เงินมันไหลออกต่อเนื่องครับ ขืนเข้าไปตอนนี้เหมือนไปรับของโจรเสี่ยงดอยสูง แต่ถ้า RSI มันลงมาต่ำกว่านี้ค่อยน่าสน..."]
    
    ---
    *ปล. เชื่อผมได้ แต่อย่าเชื่อหมดใจนะ เงินเราเราต้องตัดสินใจเองครับ!*
    """
    
    try:
        res = _safe_generate_content([prompt])
        return res.text
    except Exception as e:
        return f"AI System Error: {e}"