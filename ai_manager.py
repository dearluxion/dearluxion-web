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

# 5. Crypto God Mode (Quant Analyst - Probability & Risk Assessment)
def analyze_crypto_god_mode(coin_name, current_price, indicators, news_text, fear_greed):
    if not is_ready: return "⚠️ ระบบ AI ยังไม่พร้อม (กรุณาใส่ API Key)"
    
    # ดึงค่า Technical ใหม่ๆ ออกมา
    rsi = float(indicators.get('rsi', 50))
    macd = float(indicators.get('macd', 0))
    macd_signal = float(indicators.get('macd_signal', 0))
    adx = float(indicators.get('adx', 20))  # ความแข็งแกร่งของเทรนด์ (>25 = มีเทรนด์)
    atr = float(indicators.get('atr', 0))   # ความผันผวน
    support = float(indicators.get('support', current_price * 0.95))
    resistance = float(indicators.get('resistance', current_price * 1.05))
    
    # --- [FIX] ส่วนที่ต้องเพิ่มเพื่อแก้ NameError ---
    if rsi > 70:
        reason_based_on_rsi_resistance = "RSI Overbought (>70) เสี่ยงราคาร่วงแรง"
    elif current_price >= resistance * 0.98:
        reason_based_on_rsi_resistance = "ราคาชนแนวต้านสำคัญ (Resistance Test)"
    else:
        reason_based_on_rsi_resistance = "ความผันผวนของตลาด (Market Volatility)"
    # ---------------------------------------------
    
    prompt = f"""
    Role: You are a "Senior Quantitative Analyst" (Quant) for a high-frequency trading fund.
    Task: Analyze {coin_name} strictly based on the provided technical data. Calculate probabilities for the next 1-3 days.
    
    [LIVE MARKET DATA - THB ONLY]
    Current Price: {current_price:,.2f} THB
    RSI (14): {rsi:.2f} (Overbought > 70, Oversold < 30, Neutral 40-60)
    MACD: {macd:.6f} | Signal: {macd_signal:.6f}
    ADX (Trend Strength): {adx:.2f} (Strong Trend if > 25, Weak/Ranging if < 20)
    ATR (Daily Volatility): {atr:,.2f} THB (Daily swing range)
    Support Level (30-day low): {support:,.2f} THB
    Resistance Level (30-day high): {resistance:,.2f} THB
    Market Sentiment: {fear_greed['value']} ({fear_greed['value_classification']})
    
    [NEWS CONTEXT]
    {news_text}
    
    [REQUIRED ANALYSIS PROTOCOL]
    1. **Probability Assessment (Must sum to 100%):** Based on RSI + MACD + ADX, calculate probability:
       - Bullish (Up to Resistance): X%
       - Sideways/Range: Y%
       - Bearish (Down to Support): Z%
    
    2. **"Doi" Risk Calculation:** What's the % chance of getting trapped at a local top if buying NOW?
       - Use: How far from current price to Resistance? Is RSI already overbought?
    
    3. **Option Comparison (Critical):**
       - Option A: Buy IMMEDIATELY at {current_price:,.2f} THB
       - Option B: Wait 1-3 days for better entry
       Compare win rate %, "Doi" risk, and expected return for each.
    
    4. **Price Targets (3-day horizon):** Give specific THB targets with confidence %.
    
    [OUTPUT FORMAT - STRICT MARKDOWN]
    ## 📊 QUANT ANALYSIS: {coin_name}
    **Analysis Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} (THB)
    
    ### 1️⃣ 🎲 Probability Assessment (Next 72 Hours)
    * **📈 Bullish Case:** ...% (Price targets: ฿..., Reasoning: ...)
    * **🦀 Sideways Range:** ...% (Price range: ฿... to ฿..., Reasoning: ...)
    * **📉 Bearish Case:** ...% (Support level: ฿..., Reasoning: ...)
    
    ### 2️⃣ ⚠️ "Doi" (Trap) Risk Assessment
    - **If buy NOW:** ...% risk of being trapped (too high/too risky)
    - **Key concern:** {reason_based_on_rsi_resistance}
    
    ### 3️⃣ ⚖️ Strategy Comparison
    
    | Factor | Option A: Buy NOW | Option B: Wait 1-3D |
    | :--- | :---: | :---: |
    | **Win Probability** | ...% | ...% |
    | **Trap Risk ("Doi")** | ...% | ...% |
    | **Avg Entry Price** | ฿{current_price:,.2f} | ฿...  |
    | **Expected Return (per THB)** | ...% | ...% |
    | **Volatility (ATR)** | ±฿{atr:,.2f} | Higher/Same/Lower |
    
    **🏆 Verdict:** CHOOSE OPTION **[A or B]** because...
    
    ### 4️⃣ 🎯 3-Day Price Targets
    * **Best Case (High Confidence):** ฿... (70% probability)
    * **Mid Case (Medium Confidence):** ฿... (50% probability)
    * **Worst Case (Support Breakdown):** ฿... (20% probability)
    * **Daily Range (ATR):** Expect ±฿{atr:,.2f} per day
    
    ### 5️⃣ 📈 Technical Summary
    - **Trend:** ADX={adx:.1f} → {'STRONG' if adx > 25 else 'WEAK/RANGING'}
    - **Momentum:** RSI={rsi:.1f} → {'OVERBOUGHT (⚠️)' if rsi > 70 else 'OVERSOLD (↑)' if rsi < 30 else 'NEUTRAL'}
    - **Signal Cross:** MACD {'BULLISH (✓)' if macd > macd_signal else 'BEARISH (✗)'} (Macd > Signal)
    
    ---
    *⚖️ Disclaimer: This is AI-generated technical analysis for educational purposes only, NOT financial advice.*
    """
    
    try:
        res = _safe_generate_content([prompt])
        return res.text
    except Exception as e:
        return f"Quant System Error: {e}"