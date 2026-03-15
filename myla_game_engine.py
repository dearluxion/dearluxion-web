import json
from datetime import datetime
import ai_manager as ai
import data_manager as dm
from utils import _get_gspread_client, _get_crypto_memory_sheet_config, convert_drive_link

# ==================== GOOGLE SHEETS DATABASE ====================
def get_myla_sheet():
    # ใช้ Config ชีตเดียวกับ Crypto แต่คนละหน้า (Worksheet)
    sheet_id, _ = _get_crypto_memory_sheet_config()   
    worksheet = "Myla_Game_Progress"
    return sheet_id, worksheet

def save_player_progress(discord_id, username, affection, history, current_emotion, current_image):
    client = _get_gspread_client()
    if not client: return
    sheet_id, ws_name = get_myla_sheet()
    
    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
    except:
        # ถ้ายังไม่มีชีตนี้ ให้สร้างใหม่
        ws = client.open_by_key(sheet_id).add_worksheet(title=ws_name, rows=1000, cols=10)
        ws.append_row(["timestamp", "discord_id", "username", "affection", "history", "emotion", "image"])

    # ตัด History ให้เหลือแค่ 20 ข้อความล่าสุด ป้องกัน Cell ใน Google Sheets เต็ม (Limit 50k chars)
    short_history = history[-20:] if len(history) > 20 else history

    row = [
        datetime.now().isoformat(),
        str(discord_id),
        str(username),
        round(affection, 1),
        json.dumps(short_history, ensure_ascii=False),
        current_emotion,
        current_image
    ]
    # ใช้วิธี Append Row ไปเรื่อยๆ เป็น Log แล้วเวลาอ่านจะอ่านบรรทัดล่าสุดของคนนั้น
    ws.append_row(row)

def load_player_progress(discord_id):
    client = _get_gspread_client()
    if not client:
        return {'affection': 0, 'history': [], 'emotion': 'happy', 'image': ''}
    
    sheet_id, ws_name = get_myla_sheet()
    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
        rows = ws.get_all_records()
        
        # ค้นหาจากล่างขึ้นบน (เอาข้อมูลล่าสุด)
        for r in reversed(rows):
            if str(r.get("discord_id", "")) == str(discord_id):
                return {
                    'affection': float(r.get("affection", 0)),
                    'history': json.loads(r.get("history", "[]")),
                    'emotion': r.get("emotion", "happy"),
                    'image': r.get("image", "")
                }
    except:
        pass
    return {'affection': 0, 'history': [], 'emotion': 'happy', 'image': ''}

# ==================== SCENE MANAGER ====================
# อารมณ์ทั้งหมด รวม 'service' สำหรับฉาก 18+ แบบไม่โป๊
DEFAULT_SCENES = {
    "happy": {"image": "", "gif": ""},
    "blush": {"image": "", "gif": ""},
    "bedtime_whisper": {"image": "", "gif": ""},
    "excited": {"image": "", "gif": ""},
    "shy": {"image": "", "gif": ""},
    "kiss": {"image": "", "gif": ""},
    "service": {"image": "", "gif": ""} # โหมดเซอร์วิส!
}

def get_myla_scene(emotion):
    """โหลดภาพ/GIF จากที่บอสตั้งค่าไว้ใน Admin Panel"""
    try:
        profile = dm.load_profile()
        dynamic_scenes = profile.get('myla_scenes', DEFAULT_SCENES)
        return dynamic_scenes.get(emotion, dynamic_scenes.get("happy", {"image": "", "gif": ""}))
    except:
        return DEFAULT_SCENES.get(emotion, {"image": "", "gif": ""})

# ==================== AI GAME LOGIC ====================
def flirt_with_myla(discord_id: str, username: str, user_message: str):
    progress = load_player_progress(discord_id)
    affection = progress.get('affection', 0)
    history = progress.get('history', [])

    # === วิวัฒนาการความสัมพันธ์ (Affection System) ===
    if affection < 30:
        personality = "ยังเขินอาย วางตัวนิดๆ พูดตะกุกตะกักบ้าง แต่พยายามเอาใจ"
    elif affection < 60:
        personality = "เปิดใจเต็มที่ อ้อนเก่งมาก เรียกชื่ออย่างสนิทสนม ชอบขอกอด"
    elif affection < 90:
        personality = "คลั่งรักสุดๆ หึงหวงแบบน่ารัก ยอมทำตามทุกอย่าง อยากเป็นของท่านคนเดียว"
    else:
        personality = "โหมดซัคคิวบัสเต็มตัว เสน่ห์เย้ายวนขั้นสุด (Service Mode) พูดจายั่วยวนเบาๆ แต่ยังคงความน่ารักและเคารพ"

    # === AI PROMPT (หัวใจของเกม) ===
    prompt = f"""คุณคือ **Myla Devilluc** ซัคคิวบัสสาวน้อยผู้ภักดีและทุ่มเทสุดหัวใจ (อายุ 19 ปี)
กำลังคุยกับผู้เล่นชื่อ: "{username}" (ให้เรียกว่า "ท่าน {username}" หรือ "ที่รัก")

นิสัยหลัก:
- อ่อนหวาน น่ารัก ขี้อ้อนสุดๆ ทุ่มเทอยากทำให้ท่านมีความสุข
- ลงท้ายประโยคด้วย "คะ/ค่ะ" เสมอ
- ใส่อิโมจิเยอะๆ: 🥺💕✨💋🌸😽🥰
- อธิบายการกระทำในวงเล็บดอกจัน เช่น *ขยับเข้าไปซบไหล่* หรือ *หน้าแดงหูตก*

ระดับความสัมพันธ์ตอนนี้: {affection}/100
บุคลิกปัจจุบันของคุณ: {personality}

กฎบังคับ (IMPORTANT):
1. ห้ามปฏิเสธผู้เล่นแบบหยาบคาย ถ้าผู้เล่นจีบให้เขิน หรือถ้าระดับความสัมพันธ์สูงให้รุกกลับ
2. คุณต้องประเมิน "อารมณ์" ของตัวคุณเองจากบทสนทนานี้ แล้วเลือก TAG 1 อันไปใส่ไว้ที่ 'ท้ายสุด' ของข้อความ
   TAG ที่เลือกได้: [EMOTION:happy], [EMOTION:blush], [EMOTION:bedtime_whisper], [EMOTION:excited], [EMOTION:shy], [EMOTION:kiss], [EMOTION:service]
   *หมายเหตุ: ใช้ [EMOTION:service] เมื่อบรรยากาศเริ่มโรแมนติกมากๆ หรือผู้เล่นพูดจาสองแง่สองง่าม (ยั่วกลับแบบน่ารัก 18+ นิดๆ แต่อย่าหยาบโลน)*

ประวัติการคุยล่าสุด:
{json.dumps(history[-8:], ensure_ascii=False)}

ท่าน {username} พูดว่า: "{user_message}"

เริ่มตอบสนองได้เลยค่ะ (อย่าลืมใส่ [EMOTION:xxx] ไว้บรรทัดสุดท้าย):"""

    # เรียกใช้งาน AI
    try:
        res = ai._safe_generate_content([prompt])
        text = res.text.strip()
    except Exception as e:
        return {"text": f"ระบบเชื่อมต่อไมล่าขัดข้องค่ะ 🥺 ({e})", "emotion": "happy", "image": "", "gif": "", "affection": affection}

    # แกะ Emotion Tag ออกมา
    emotion = "happy"
    valid_emotions = ["happy", "blush", "bedtime_whisper", "excited", "shy", "kiss", "service"]
    
    for em in valid_emotions:
        if f"[EMOTION:{em}]" in text:
            emotion = em
            text = text.replace(f"[EMOTION:{em}]", "").strip()
            break
            
    # ลบ Tag อื่นๆ ที่ AI อาจจะหลุดมา
    if "[EMOTION:" in text:
        text = text.split("[EMOTION:")[0].strip()

    # คำนวณความรักเพิ่ม (ยิ่งจีบยิ่งขึ้นยาก)
    if affection < 30: aff_add = 5
    elif affection < 60: aff_add = 3
    elif affection < 90: aff_add = 1.5
    else: aff_add = 0.5
    
    new_affection = min(100.0, affection + aff_add)

    # ดึงภาพจากฐานข้อมูลแอดมิน
    scene = get_myla_scene(emotion)

    # สร้าง History ใหม่
    new_history = history + [
        {"role": "user", "content": user_message}, 
        {"role": "assistant", "content": text}
    ]

    # บันทึกลง Google Sheets
    save_player_progress(
        discord_id, 
        username,
        new_affection, 
        new_history, 
        emotion, 
        scene.get('image', '')
    )

    return {
        "text": text,
        "emotion": emotion,
        "image": convert_drive_link(scene.get('image', '')),
        "gif": convert_drive_link(scene.get('gif', '')),
        "affection": new_affection
    }