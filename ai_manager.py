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

# 5. Crypto God Mode V2 (Senior Crypto Hedge Fund Manager - Risk-Averse)
def analyze_crypto_god_mode(coin_name, current_price, indicators, news_text, fear_greed):
    if not is_ready: return "⚠️ ระบบ AI ยังไม่พร้อม (กรุณาใส่ API Key)"
    
    # ดึงค่า Indicators ใหม่ (V2)
    rsi = float(indicators.get('rsi', 50))
    stoch_k = float(indicators.get('stoch_k', 50))  # NEW
    obv_status = str(indicators.get('obv_slope', 'N/A'))  # NEW
    
    macd = float(indicators.get('macd', 0))
    macd_signal = float(indicators.get('macd_signal', 0))
    adx = float(indicators.get('adx', 20))
    atr = float(indicators.get('atr', 0))
    
    pivot_p = float(indicators.get('pivot_p', 0))  # NEW
    pivot_s1 = float(indicators.get('pivot_s1', 0))  # NEW
    pivot_r1 = float(indicators.get('pivot_r1', 0))  # NEW
    
    support = float(indicators.get('support', current_price * 0.95))
    resistance = float(indicators.get('resistance', current_price * 1.05))
    
    # --- [V2] ตรวจจับกับดัก (Trap Detection) ---
    bearish_divergence = False
    trap_warning = ""
    if "เงินไหลออก" in obv_status and rsi > 60:
        bearish_divergence = True
        trap_warning = "⚠️ **ระวัง! Bearish Divergence**: ราคาขึ้นแต่เงินออก (Fake Pump) - เสี่ยงการป้อมสูง"
    elif adx < 20 and rsi > 70:
        trap_warning = "⚠️ **ตลาดออกข้าง (Sideways) + RSI Overbought**: ระวังตัด Loss"
    
    # [THAI PROMPT UPDATE V2.0] - Risk Manager + Trap Detector
    prompt = f"""
    Role: คุณคือ "Senior Crypto Hedge Fund Manager" ที่เน้นความปลอดภัยของเงินทุนสูงสุด (Risk-First Approach)
    Task: วิเคราะห์เหรียญ {coin_name} สำหรับการเทรดระยะสั้น (72 ชั่วโมง) ด้วยข้อมูล Quant ล่าสุด
    Strategy: หลีกเลี่ยง FOMO, จับ Pivot Points ที่แม่นยำ, เช็คกับดักราคาก่อนเข้า
    
    [LIVE MARKET DATA - THB]
    Price: {current_price:,.2f} THB
    
    [MOMENTUM & TREND]
    - RSI (14): {rsi:.2f} (ปกติ >70 Overbought, <30 Oversold)
    - StochRSI (K): {stoch_k:.2f} (ไวมาก: >80 ขาย, <20 ซื้อ) **[NEW V2]**
    - MACD vs Signal: {macd:.2f} / {macd_signal:.2f}
    - ADX Trend Strength: {adx:.2f} (ถ้า < 20 แสดงว่าตลาด Sideway ห้ามใช้ MACD)
    
    [MONEY FLOW - สำคัญ! **[NEW V2]**]
    - OBV Flow (5-Day): {obv_status} (ถ้าค่าติดลบ แสดงว่าเงินไหลออก ระวังกับดักราคาขึ้นหลอกๆ)
    
    [KEY LEVELS - Pivot Points **[NEW V2]**]
    - Pivot Point (Central): {pivot_p:,.2f} THB
    - Support S1 (Buy Zone): {pivot_s1:,.2f} THB
    - Resistance R1 (Sell Zone): {pivot_r1:,.2f} THB
    - ATR (ความผันผวน): {atr:,.2f} THB
    
    [MARKET SENTIMENT]
    - Fear & Greed: {fear_greed['value']} ({fear_greed['value_classification']})
    - News: {news_text}
    
    [⚠️ TRAP ALERT]
    {trap_warning if trap_warning else "✅ ไม่พบกับดักชัดเจน"}
    
    [คำสั่งวิเคราะห์ - STRICT RISK MANAGEMENT]
    
    1. **เช็คกับดัก (Trap Check) [CRITICAL]:** 
       - ถ้าราคาขึ้นแต่ OBV ไหลออก หรือ RSI ขัดแย้ง ให้เตือน "Bearish Divergence" ทันที
       - ถ้า ADX < 25 ให้เชื่อ StochRSI มากกว่า MACD (เพราะตลาดออกข้าง)
    
    2. **กรองสัญญาณ (Signal Filtering):**
       - ถ้า ADX < 25 = Sideways Market ห้ามเทรดตามเทรนด์ MACD ให้ใช้ Support/Resistance แทน
       - ถ้า StochRSI > 80 = ขาย (ไม่ว่า RSI จะเท่าไหร่)
       - ถ้า StochRSI < 20 = ซื้อ (แต่ต้องรอ Pivot S1 ด้วย)
    
    3. **จุดเข้าซื้อที่ปลอดภัย:**
       - ห้ามแนะนำให้ไล่ราคา (FOMO) 
       - ให้รอรับที่ Pivot S1: {pivot_s1:,.2f} THB หรือแนวรับเท่านั้น
       - Entry ที่ดีที่สุด = Pivot S1 + เมื่อ OBV เริ่มไหลเข้า
    
    4. **จุดขายทำกำไรที่ชาญฉลาด:**
       - Target 1: Pivot P (ตรงกลาง): {pivot_p:,.2f} THB (ปลอดภัยสัก 50%)
       - Target 2: Pivot R1 (แนวต้าน): {pivot_r1:,.2f} THB (เสี่ยง แต่กำไรเพิ่ม)
    
    [รูปแบบการตอบ - MARKDOWN ภาษาไทย (God Mode V2.0)]
    
    ## 🧠 QUANT GOD MODE V2.0: {coin_name}
    **เวลาวิเคราะห์:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} | **Risk Level: Manager Mode** 
    
    ### 🚦 1️⃣ สรุปสัญญาณ (Signal Status)
    * **สถานะปัจจุบัน:** [เลือก: 🟢 BULLISH / 🟡 NEUTRAL / 🔴 BEARISH]
    * **ระดับความน่าเชื่อถือ:** .../5 ⭐ (พิจารณาจาก OBV + ADX + StochRSI)
    * **คำเตือนความเสี่ยง:** {trap_warning if trap_warning else "(ไม่พบเสี่ยงสูง)"}
    
    ### ⚖️ 2️⃣ กลยุทธ์ 72 ชั่วโมง (Tactical Plan)
    
    **จุดเข้าซื้อที่ดีที่สุด (Best Entry):**
    * ฿{pivot_s1:,.2f} (Pivot S1 - ช้อนซื้อ) ← **แนะนำเข้าที่นี่เพื่อความปลอดภัย**
    * จุดเข้าสำรอง: ฿{pivot_p:,.2f} (Pivot P - ตรงกลาง)
    
    **เป้าขายทำกำไร (Profit Targets):**
    * Target 1️⃣ (50%): ฿{pivot_p:,.2f} (Pivot Point - ตัดกำไรสักครึ่ง)
    * Target 2️⃣ (50%): ฿{pivot_r1:,.2f} (Pivot R1 - แนวต้าน เสี่ยงมากเก็บกำไรทั้งหมด)
    
    **จุดยอมแพ้ (Stop Loss - สำคัญ!):**
    * ฿{pivot_s1 - (atr * 1.5):,.2f} (คำนวณจาก S1 - 1.5×ATR)
    * **ห้ามเอาไปใหญ่เกิน ลดความสูญเสีย**
    
    ### 🎲 3️⃣ ความน่าจะเป็น 72 ชม. (Probability Scenarios)
    * 📈 **ขึ้นทดสอบ {pivot_r1:,.0f}:** ...% (ระบุจาก ADX, RSI, StochRSI)
    * 🦀 **แกว่งตัวในกรอบ ({pivot_s1:,.0f}-{pivot_r1:,.0f}):** ...%
    * 📉 **ทุบหลุดแนวรับ {pivot_s1:,.0f}:** ...%
    
    ### 💡 4️⃣ เหตุผลเชิงเทคนิค (Deep Dive Analysis)
    
    **Trend & Momentum:**
    * ADX = {adx:.1f} → {'เทรนด์แข็งแกร่ง ใช้ MACD ได้' if adx > 25 else 'ไร้เทรนด์ ตลาด Sideways ห้ามติดตาม Trend'}
    * RSI = {rsi:.1f} → {'⚠️ Overbought (เสี่ยงผลัดตัว)' if rsi > 70 else '⚠️ Oversold (เก็บตัว รอเด้ง)' if rsi < 30 else '✅ Neutral (ปกติ)'}
    * StochRSI = {stoch_k:.1f} → {'⚡ สัญญาณขายแข็ง' if stoch_k > 80 else '⚡ สัญญาณซื้อแข็ง' if stoch_k < 20 else '➡️ Ranging'}
    * MACD = {'✅ ตัดขึ้น (Bullish)' if macd > macd_signal else '❌ ตัดลง (Bearish)'}
    
    **Smart Money Flow (ที่สำคัญที่สุด!):**
    * OBV Slope: {obv_status}
    * {'🟢 เงินเข้าเต็มไปหมด = สัญญาณซื้อแข็ง' if 'เข้า' in obv_status else '🔴 เงินออกแบบนิ่มนวล = ระวัง Fake Pump'}
    * **สรุป:** {'ตัวจริง Bullish' if 'เข้า' in obv_status else 'กับดักราคา (Trap)'}
    
    ### 📋 5️⃣ สรุปการเทรด (Trading Summary)
    
    | ปัจจัย | ข้อมูล |
    | :--- | :--- |
    | **Entry Zone** | ฿{pivot_s1:,.2f} (Pivot S1) |
    | **Target 1** | ฿{pivot_p:,.2f} (Pivot P - 50%) |
    | **Target 2** | ฿{pivot_r1:,.2f} (Pivot R1 - 100%) |
    | **Stop Loss** | ฿{pivot_s1 - (atr * 1.5):,.2f} (S1 - 1.5×ATR) |
    | **Risk:Reward** | 1:... (คำนวณเอง) |
    | **Signal Strength** | {'🟢🟢🟢 Very Strong' if adx > 35 and 'เข้า' in obv_status else '🟡🟡 Moderate' if adx > 20 else '🔴 Weak'} |
    
    ---
    *🛡️ บทวิเคราะห์นี้เน้นความปลอดภัยและหลีกเลี่ยง FOMO เป็นหลัก (Risk Manager Mode)*
    *⚠️ ไม่ใช่คำแนะนำการลงทุน (NFA) | บทบาทเป็นการศึกษาเท่านั้น*
    """
    
    try:
        res = _safe_generate_content([prompt])
        return res.text
    except Exception as e:
        return f"Quant System Error: {e}"