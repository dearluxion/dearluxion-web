import google.generativeai as genai
import random
import json
import re
import requests
import datetime
import time

# --- Global Variables ---
api_keys = []        # รายการ Key ทั้งหมด
current_key_index = 0 # ตัวชี้ว่าตอนนี้ใช้ Key ไหนอยู่
model = None
is_ready = False
webhook_url = None   # ลิงก์ Webhook สำหรับแจ้งเตือน

def init_ai(keys_list, discord_webhook_url):
    """
    เริ่มระบบ AI รองรับ Multi-Key
    keys_list: list ของ API Key (เช่น [key1, key2, key3, ...])
    """
    global api_keys, current_key_index, model, is_ready, webhook_url
    
    try:
        # กรองเอาเฉพาะ Key ที่ไม่ว่าง
        api_keys = [k for k in keys_list if k and k.strip()]
        
        if not api_keys:
            print("❌ No API Keys provided")
            return False

        webhook_url = discord_webhook_url
        current_key_index = 0 # เริ่มที่ Key แรกเสมอ
        
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
    # ใช้ Model ตัวใหม่ล่าสุด
    model = genai.GenerativeModel('gemini-2.0-flash-exp') 
    print(f"🤖 AI switched to Key Index: {current_key_index+1}")

def _rotate_key_and_notify(error_msg):
    """ฟังก์ชันภายใน: สลับ Key อัตโนมัติ + แจ้ง Discord"""
    global current_key_index, is_ready
    
    dead_key_index = current_key_index
    
    # คำนวณ Index ถัดไป (วนลูป)
    next_index = (current_key_index + 1) % len(api_keys)
    
    current_key_index = next_index
    _setup_model() # Re-configure ทันที

    # --- แจ้งเตือนเข้า Discord ---
    if webhook_url and "ใส่_LINK" not in webhook_url:
        try:
            payload = {
                "username": "Myla System Alert 🚨",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/564/564619.png",
                "embeds": [{
                    "title": "⚠️ API Key Exhausted (Rate Limit)",
                    "description": f"**Key ที่ตาย:** #{dead_key_index + 1}\n**สาเหตุ:** `{str(error_msg)}`\n**การแก้ไข:** 🔄 ระบบสลับไปใช้ **Key #{current_key_index + 1}** ให้แล้วค่ะ!",
                    "color": 16711680, # สีแดง
                    "timestamp": datetime.datetime.now().isoformat()
                }]
            }
            requests.post(webhook_url, json=payload)
        except Exception as e:
            print(f"Failed to send alert: {e}")

def _safe_generate_content(prompt):
    """
    ฟังก์ชันวิเศษ: พยายาม Generate ถ้า Error จะสลับ Key แล้วลองใหม่
    """
    global is_ready
    if not is_ready: raise Exception("AI System not ready")

    # ลองวนลูปตามจำนวน Key ที่มี (ให้โอกาสทุก Key 1 ครั้ง)
    max_retries = len(api_keys)
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response
        except Exception as e:
            error_str = str(e)
            # เช็คว่าเป็น Error เกี่ยวกับ Quota หรือไม่ (429, 503, ResourceExhausted)
            if "429" in error_str or "quota" in error_str.lower() or "exhausted" in error_str.lower():
                print(f"⚠️ Key #{current_key_index+1} Failed. Switching...")
                _rotate_key_and_notify(error_str)
                time.sleep(1) # พักหายใจนิดนึงก่อนยิงใหม่
                # วนลูปต่อไปเพื่อลอง Key ใหม่
            else:
                # ถ้าเป็น Error อื่น (เช่น Prompt ผิด) ให้โยน Error ออกไปเลย ไม่ต้องสลับ Key
                raise e
    
    raise Exception("💀 All API Keys are dead/exhausted.")

# --- Helper: ล้าง JSON ---
def clean_json_text(text):
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()

# ==========================================
#  ฟังก์ชันเรียกใช้งาน (ปรับให้เรียกผ่าน _safe_generate_content)
# ==========================================

# 1. Crowd Simulation
def generate_post_engagement(post_content):
    if not is_ready:
        return [{"user": "🧚‍♀️ Myla (Offline)", "text": "ระบบพักผ่อน... แต่รักบอสนะ!", "reaction": "😻"}]
    
    num_bots = random.randint(4, 10)
    prompt = f"""
    Context: จำลองสังคมออนไลน์ในกลุ่มปิดชื่อ "Small Group" ของบอส Dearluxion
    Task: สร้างรายการ Interaction ของสมาชิกจำนวน {num_bots} คน ที่มาเห็นโพสต์นี้: "{post_content}"
    
    Requirements:
    1. ต้องมีผู้ใช้ชื่อ "🧚‍♀️ Myla" (นิสัย: ร่าเริง, ให้กำลังใจบอส, ใช้ Emoji เยอะ)
    2. ต้องมีผู้ใช้ชื่อ "🍸 Ariel" (นิสัย: เย็นชา, ปากร้าย, พูดห้วนๆ, เกลียดความโลกสวย, อาจจะแซะโพสต์)
    3. อีก {num_bots - 2} คนที่เหลือ ให้สุ่มชื่อ User แบบคนไทยจริงๆ
       - นิสัย: หลากหลาย (กวนตีน, ถามราคา, ชม, ขำ)
       - ภาษา: พิมพ์แบบคนไทยเล่นเน็ตจริงๆ มีคำสแลง **ห้ามดูออกว่าเป็น AI**
    
    Response Format (JSON Array only):
    [
        {{ "user": "ชื่อ", "text": "ข้อความ", "reaction": "เลือก 1 อย่าง [😻, 🙀, 😿, 😾, 🧠, null]" }}
    ]
    """
    try:
        response = _safe_generate_content(prompt) # <--- ใช้ Safe Generate
        cleaned_text = clean_json_text(response.text)
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI Engagement Error: {e}")
        return [{"user": "🧚‍♀️ Myla (System)", "text": "ระบบกำลังจูน API ใหม่ค่ะบอส... (ลองกดใหม่นะ)", "reaction": "😻"}]

# 2. Mood Mocktail
def get_cocktail_recipe(user_mood):
    if not is_ready: return "AI เมาค้าง... ลองใหม่นะ"
    prompt = f"คุณคือ 'บาร์เทนเดอร์ AI' ประจำคลับของ Dearluxion ลูกค้าบอกอารมณ์มาว่า: '{user_mood}' คิดสูตร 'Mocktail' (ชื่อ, ส่วนผสมลับนามธรรม, วิธีดื่ม, คำคม) ให้หน่อย"
    try:
        res = _safe_generate_content(prompt) # <--- ใช้ Safe Generate
        return res.text
    except Exception as e: return f"ชงไม่ได้ครับ แก้วแตก! ({e})"

# 3. Ariel Chat
def get_ariel_response(user_msg):
    if not is_ready: return "API ยังไม่พร้อม..."
    ariel_persona = """
    คุณคือ "เอเรียล" หญิงสาวบุคลิกเย็นชา ซับซ้อน มีอดีตที่บอบช้ำ               
    - พูดน้อย ทรงพลัง ไม่ลงท้าย "คะ/ขา" บ่อยนัก เรียกคนอื่นว่า "เธอ" หรือ "นาย" หรือเรียกชื่อห้วนๆ
    - เกลียดความโลกสวย
    - สไตล์: เย็นชา ปากไม่ตรงกับใจ (Tsundere) ประชดประชัน
    """
    full_prompt = f"{ariel_persona}\n\nUser: {user_msg}\nAriel:"
    try:
        res = _safe_generate_content(full_prompt) # <--- ใช้ Safe Generate
        return res.text.strip()
    except Exception as e: return f"เอเรียลไม่อยากคุยตอนนี้ ({e})"

# 4. Battle Mode
def get_battle_result(topic):
    if not is_ready: return "AI ไม่พร้อม", "AI ไม่พร้อม"
    try:
        # แยก Call เพื่อความชัวร์ (ถ้า Error อันแรก ก็จะสลับ Key ให้ อันสองก็ได้ใช้ Key ใหม่)
        res_myla = _safe_generate_content(f"คุณคือ Myla AI สาวน้อยร่าเริง ตอบเรื่อง '{topic}' แบบให้กำลังใจ น่ารัก").text
        res_ariel = _safe_generate_content(f"คุณคือ Ariel AI (เอเรียล) หญิงสาวเย็นชา ปากร้าย ตอบเรื่อง '{topic}' แบบขวานผ่าซาก ประชดนิดๆ").text
        return res_myla, res_ariel
    except Exception as e: return f"Error: {e}", f"Error: {e}"