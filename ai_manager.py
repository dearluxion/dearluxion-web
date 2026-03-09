import google.generativeai as genai
import random
import json
import re
import requests
import datetime
import time
import difflib
from PIL import Image
import io
import mimetypes
import tempfile
import os
from youtube_transcript_api import YouTubeTranscriptApi

# --- MEME GIF POOL ---

MEME_GIF_POOL = [
    "https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif",   # cat dance
    "https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif",   # shocked pikachu
    "https://media.giphy.com/media/26ufnwz3wDUli7GU0/giphy.gif",   # crying laughing
    "https://media.giphy.com/media/VseXvvxwowwCc/giphy.gif",       # thumbs up
    "https://i.imgur.com/8J3vK.gif",                                # classic meme
    "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif",       # cat waving
    "https://media.giphy.com/media/3o6Zt6KHxJTbXCnSvu/giphy.gif",  # fail
]

# --- Personas ---
personas = {
    "Myla": {"name": "Myla"},
    "Ariel": {"name": "Ariel"},
    "NongBank": {"name": "NongBank"},
    "NongFern": {"name": "NongFern"},
    "Other": {"name": "Other"}
}

def get_persona_key(user):
    if "Myla" in user: return "Myla"
    if "Ariel" in user: return "Ariel"
    if "NongBank" in user: return "NongBank"
    if "NongFern" in user: return "NongFern"
    return "Other"

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

def safe_float(x, default=0.0):
    """แปลงค่าเป็น float แบบทนทานต่อเลขที่มี comma เช่น '2,762,445.08'"""
    try:
        if x is None:
            return float(default)
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            x = x.replace(',', '').strip()
            if x == '':
                return float(default)
        return float(x)
    except Exception:
        return float(default)

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


def build_trade_snapshot(current_price, indicators, analysis_text: str = ""):
    """สรุปแผนเทรดแบบคำนวณตรงไปตรงมา เพื่อใช้แสดงผล/บันทึกแบบอ่านง่าย"""
    price = safe_float(current_price, 0.0)
    entry = safe_float(indicators.get('pivot_s1', price or 0), price or 0)
    target = safe_float(indicators.get('pivot_r1', price or 0), price or 0)
    support = safe_float(indicators.get('support', entry or 0), entry or 0)
    resistance = safe_float(indicators.get('resistance', target or 0), target or 0)
    rsi = safe_float(indicators.get('rsi', 50), 50.0)
    macd = safe_float(indicators.get('macd', 0), 0.0)
    macd_signal = safe_float(indicators.get('macd_signal', 0), 0.0)
    adx = safe_float(indicators.get('adx', 20), 20.0)
    obv = str(indicators.get('obv_slope', ''))

    score = 50
    score += 10 if macd > macd_signal else -10
    if 'เงินไหลเข้า' in obv:
        score += 12
    elif 'เงินไหลออก' in obv:
        score -= 12
    if adx >= 25:
        score += 10
    elif adx < 18:
        score -= 8
    if rsi < 30:
        score += 8
    elif rsi > 75:
        score -= 12
    elif 45 <= rsi <= 65:
        score += 6
    score = max(5, min(95, int(score)))

    trap_rate = 10
    if 'เงินไหลออก' in obv and rsi > 60:
        trap_rate = 75
    elif adx < 20 and rsi > 70:
        trap_rate = 65
    elif adx < 18:
        trap_rate = 40
    elif rsi > 70:
        trap_rate = 35

    if trap_rate >= 65:
        signal = 'TRAP'
    elif score >= 72:
        signal = 'VERY_BULLISH'
    elif score >= 58:
        signal = 'BULLISH'
    elif score <= 35:
        signal = 'BEARISH'
    else:
        signal = 'NEUTRAL'

    reward = max(0.0, target - entry)
    risk = max(0.0, entry - support)
    rr = (reward / risk) if risk > 0 else 0.0

    if trap_rate >= 65:
        threat = 'สูงมาก (Very High)'
    elif trap_rate >= 40:
        threat = 'สูง (High)'
    elif score >= 70:
        threat = 'ต่ำ (Low)'
    else:
        threat = 'กลาง (Medium)'

    return {
        'price': price,
        'entry': round(entry, 8),
        'target': round(target, 8),
        'stoploss': round(support, 8),
        'resistance': round(resistance, 8),
        'signal': signal,
        'confidence': score,
        'trap_rate': trap_rate,
        'risk_reward': round(rr, 2),
        'threat_level': threat,
    }


def build_trade_snapshot_markdown(coin_name, snapshot: dict):
    status = get_market_status_th(snapshot.get('signal', 'NEUTRAL'))
    return f"""### 📌 สรุปเร็วสำหรับคนเทรดจริง
- **สถานะตลาด (Market Status):** {status['icon']} {status['title']}
- **ความมั่นใจ (Confidence Accuracy):** {snapshot.get('confidence', 0)}%
- **โอกาสเจอกับดัก (Trap Rate):** {snapshot.get('trap_rate', 0)}%
- **โซนรอเข้า (Entry Zone):** ฿{snapshot.get('entry', 0):,.2f}
- **เป้าทำกำไร (Target Hit):** ฿{snapshot.get('target', 0):,.2f}
- **จุดยอมแพ้ (Stop Loss):** ฿{snapshot.get('stoploss', 0):,.2f}
- **อัตราเสี่ยง/ผลตอบแทน (Risk/Reward):** {snapshot.get('risk_reward', 0):.2f}
- **ระดับความเสี่ยง (Threat Level):** {snapshot.get('threat_level', '-')}
"""


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
def _extract_drive_file_id(link: str):
    if not link or not isinstance(link, str):
        return None
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"thumbnail\?id=([a-zA-Z0-9_-]+)",
        r"lh3\.googleusercontent\.com/d/([a-zA-Z0-9_-]+)",
    ]
    for p in patterns:
        mm = re.search(p, link)
        if mm:
            return mm.group(1)
    return None


def _drive_uc_download_url(file_id: str):
    # ใช้สูตร download ตรง ๆ (เหมาะกับ video/gif/image)
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def _drive_lh3_url(file_id: str):
    # fallback สำหรับบางไฟล์/บางสิทธิ์ (โดยเฉพาะรูป/GIF)
    return f"https://lh3.googleusercontent.com/d/{file_id}"



def _download_url(url: str, timeout: int = 20):
    """ดาวน์โหลดไฟล์จาก URL แล้วคืน (bytes, content_type)"""
    headers = {"User-Agent": "Mozilla/5.0 (MylaAI; vision-loader)"}
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return r.content, ctype


def _load_media_for_ai(url: str):
    """แปลง URL ให้กลายเป็น input สำหรับ Gemini:
    - image/* -> PIL.Image
    - image/gif -> PIL.Image (ดึงเฟรมแรก) + ลดความเสี่ยง decode error
    - video/* -> genai.upload_file(temp_path) (ถ้ารองรับ)
    คืนค่า: (media_input, media_kind) หรือ (None, None)
    """
    if not url or not isinstance(url, str):
        return None, None

    # 0) แปลง Google Drive ให้เป็น direct download ถ้าทำได้
    fid = None
    if "drive.google.com" in url or "googleusercontent.com" in url:
        fid = _extract_drive_file_id(url)
        if fid:
            url = _drive_uc_download_url(fid)

    # 1) ดาวน์โหลด
    data, ctype = _download_url(url)

    # 1.5) กันกรณีได้หน้า permission/login (HTML) แทนไฟล์จริง
    head = (data or b"")[:300].lower()
    if ctype in ("text/html", "application/xhtml+xml") or b"<html" in head or b"<!doctype html" in head:
        # fallback: บางครั้ง uc?download ดึงไม่ได้ แต่ lh3 ดึงได้
        if fid:
            try:
                alt = _drive_lh3_url(fid)
                data2, ctype2 = _download_url(alt)
                head2 = (data2 or b"")[:300].lower()
                if not (ctype2 in ("text/html", "application/xhtml+xml") or b"<html" in head2 or b"<!doctype html" in head2):
                    data, ctype = data2, ctype2
                else:
                    return None, None
            except Exception:
                return None, None
        else:
            return None, None

    # 2) ถ้าเป็นรูป
    if ctype.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(data))
            # GIF: เอาเฟรมแรก + แปลงเป็น RGB เพื่อกันบางรุ่นพัง
            if ctype == "image/gif":
                try:
                    img.seek(0)
                except Exception:
                    pass
                img = img.convert("RGB")
            return img, "image"
        except Exception as e:
            print(f"⚠️ Failed to decode image: {e}")
            return None, None

    # 3) ถ้าเป็นวิดีโอ/อื่น ๆ ที่เป็นไฟล์
    if ctype.startswith("video/") or ctype in ("application/octet-stream", "application/mp4", "video/mp4"):
        try:
            # genai.upload_file ต้องการ path -> เขียน temp
            suffix = mimetypes.guess_extension(ctype) or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                tf.write(data)
                tmp_path = tf.name
            try:
                uploaded = genai.upload_file(tmp_path, mime_type=ctype or None)
            finally:
                # ลบไฟล์ temp (ถ้า Windows อาจลบไม่ได้ทันที แต่ server เป็น linux)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return uploaded, "video"
        except Exception as e:
            print(f"⚠️ Failed to upload video for AI: {e}")
            return None, None

    return None, None


# =========================================================
# Social Engagement Orchestrator (Anti-duplicate / Human-like)
# =========================================================
def _normalize_username(name: str) -> str:
    s = (name or "").strip()
    if not s:
        return "Anonymous"
    low = s.lower()
    # Map variants into stable identities
    if "myla" in low:
        return "🧚‍♀️ Myla"
    if "ariel" in low:
        return "🍸 Ariel"
    return s

def _norm_comment_text(text: str) -> str:
    s = (text or "").strip().lower()
    # remove urls
    s = re.sub(r"https?://\S+", " ", s)
    # keep thai/latin/numbers and spaces
    s = re.sub(r"[^0-9a-zA-Zก-๙\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _is_too_similar(text: str, existing_norms: list[str], *, ratio_th: float = 0.84, jacc_th: float = 0.70) -> bool:
    n = _norm_comment_text(text)
    if not n:
        return True
    if len(n) <= 10:
        for ex in existing_norms:
            if ex.startswith(n) or n.startswith(ex):
                return True
    tokens = set(n.split())
    for ex in existing_norms:
        if not ex:
            continue
        r = difflib.SequenceMatcher(None, n, ex).ratio()
        if r >= ratio_th:
            return True
        ex_t = set(ex.split())
        if tokens and ex_t:
            inter = len(tokens & ex_t)
            union = len(tokens | ex_t)
            if union and (inter / union) >= jacc_th:
                return True
    return False

def _clip_comment(text: str, limit: int = 280) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    return s if len(s) <= limit else s[: limit - 1] + "…"

def generate_post_engagement(post_content, image_url=None, youtube_url=None, num_bots: int | None = None, media_url: str | None = None):
    """สร้างคอมเมนต์หน้าม้า (เลือกจำนวนได้) + ให้ AI เห็น media ได้ (รูป/GIF/วิดีโอ/Drive)

    ✅ Anti-dup / Human-like rules (post-level):
    - 1 คน = 1 คอมเมนต์ ต่อโพสต์ (กัน Myla/Ariel พิมพ์ซ้ำ)
    - กันสำนวนซ้ำ ด้วย similarity filter
    - พยายามให้มี Myla + Ariel อย่างละ 1 (ถ้า num_bots >= 2)

    Priority ของ media:
    1) media_url (ถ้าส่งมา)
    2) image_url
    3) YouTube thumbnail (ถ้ามี yt)
    """
    if not is_ready:
        return [{"user": "🧚‍♀️ Myla (Offline)", "text": "ระบบพักผ่อน... แต่รักบอสนะ!", "reaction": "😻"}]

    # --- normalize num_bots ---
    if num_bots is None:
        num_bots = random.randint(8, 35)
    else:
        try:
            num_bots = max(1, min(80, int(num_bots)))
        except Exception:
            num_bots = random.randint(8, 35)

    # We request more candidates than needed, then filter down to "human-like" set.
    candidate_count = min(120, max(num_bots * 2, num_bots + 10))

    yt_context = ""
    if youtube_url:
        print(f"🎥 Analyzing YouTube: {youtube_url}")
        yt_thumb, yt_text = get_youtube_data(youtube_url)
        if yt_thumb:
            yt_context = f"\n[ข้อมูลเชิงลึกจาก YouTube Transcript]\n{yt_text}"
            # ถ้าไม่มีรูป ให้ใช้ thumbnail เป็น fallback
            if not image_url and not media_url:
                image_url = yt_thumb

    # --- attach media ---
    inputs = []
    chosen_media = media_url or image_url

    prompt_text = f"""
Role: คุณคือ Simulator จำลองสังคม Community ใน Discord ของกลุ่มวัยรุ่น/Gamer ในปี 2026
Task: สร้าง "Candidate" คอมเมนต์จำนวน {candidate_count} รายการ (เพื่อให้ระบบคัดให้เนียน)

Post Content (จากแอดมิน): "{post_content}"
{yt_context}

กฎห้ามฝ่าฝืน (สำคัญมาก):
1) 1 คน = 1 คอมเมนต์ เท่านั้น (ห้ามชื่อซ้ำเด็ดขาด)
2) สำนวน/ใจความต้องต่างกันชัดเจน (ห้ามพูดคล้ายกันหลายเมนต์)
3) ถ้า {num_bots} >= 2 ให้ "ต้องมี" Myla และ Ariel อย่างละ 1 เท่านั้น:
   - user: "🧚‍♀️ Myla" (ขี้อ้อน เรียกบอส/ท่านเดียร์)
   - user: "🍸 Ariel" (เย็นชา ปากแซ่บ เรียกเดียร์/นาย)
4) ที่เหลือเป็นสมาชิกทั่วไป (Members) โทนคละ: สายปั่น, สายมีม, สายสาระ
5) Username ต้องดูเป็น GamerTag / Discord name (ห้ามชื่อจริง-นามสกุลจริง)

Addressing: เรียกเจ้าของโพสต์ว่า "แอด", "พี่เดียร์", "บอส", "เดียโบล" คละกันไป

Response Format (JSON Array เท่านั้น):
[
  {{ "user": "Name", "text": "Comment", "reaction": "Emoji [😻, 🙀, 😿, 😾, 🧠] or null" }}
]
"""

    inputs.append(prompt_text)

    if chosen_media:
        try:
            media_input, kind = _load_media_for_ai(chosen_media)
            if media_input is not None:
                inputs.append(media_input)
                print(f"🖼️ Attached media for AI: {kind}")
        except Exception as e:
            print(f"⚠️ Failed to attach media: {e}")

    # --- helper: parse candidates safely ---
    def _parse_candidates(text: str):
        try:
            cleaned = clean_json_text(text)
            data = json.loads(cleaned)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    # --- helper: post-process (dedupe user + dedupe similar text) ---
    def _filter_candidates(cands: list, target_n: int):
        picked = []
        seen_users = set()
        norm_texts = []

        def _try_add(item):
            if not isinstance(item, dict):
                return
            user = _normalize_username(item.get("user", ""))
            text = _clip_comment(item.get("text", ""))
            react = item.get("reaction", None)

            if not user or not text:
                return

            key = user.strip().lower()
            if key in seen_users:
                return

            if _is_too_similar(text, norm_texts):
                return

            seen_users.add(key)
            norm_texts.append(_norm_comment_text(text))
            picked.append({"user": user, "text": text, "reaction": react})

        # 1) first pass: keep in order
        for it in cands:
            _try_add(it)
            if len(picked) >= target_n:
                break

        return picked, seen_users, norm_texts

    # --- 1st call: create candidates ---
    try:
        response = _safe_generate_content(inputs)
        cands = _parse_candidates(response.text or "")
    except Exception as e:
        print(f"AI Engagement Error (1st call): {e}")
        return [{"user": "🧚‍♀️ Myla (System)", "text": "คนเยอะจัด เซิร์ฟเวอร์บินชั่วคราวค่ะบอส!", "reaction": "🙀"}]

    # --- post-process + ensure Myla/Ariel once ---
    desired = num_bots
    picked, seen_users, norm_texts = _filter_candidates(cands, desired)

    def _need_user(name: str) -> bool:
        return name.lower() not in seen_users

    def _gen_single_comment(role_name: str):
        # tiny generation for missing core personas (cheap + stable)
        persona_rule = ""
        if role_name == "🧚‍♀️ Myla":
            persona_rule = "คุณคือ 🧚‍♀️ Myla: ขี้อ้อน อบอุ่น เรียกคู่สนทนาว่า 'บอส' หรือ 'ท่านเดียร์' ให้ฟีลมนุษย์"
        elif role_name == "🍸 Ariel":
            persona_rule = "คุณคือ 🍸 Ariel: เย็นชา ปากแซ่บ Tsundere เรียกคู่สนทนาว่า 'เดียร์' หรือ 'นาย' ให้ฟีลมนุษย์"
        else:
            persona_rule = "คุณคือสมาชิกใน Discord ที่พูดสั้นๆ เป็นธรรมชาติ"

        banned_users = ", ".join(sorted(list(seen_users))[:40])
        banned_norms = "; ".join(norm_texts[:25])

        prompt_one = f"""
{persona_rule}
โพสต์ของแอด: "{post_content}"
{yt_context}

เงื่อนไข:
- ห้ามใช้ username ซ้ำกับ: {banned_users if banned_users else "(none)"}
- ห้ามพูดซ้ำ/คล้ายกับประโยคเหล่านี้: {banned_norms if banned_norms else "(none)"}

ตอบเป็น JSON Object เท่านั้น:
{{"user":"{role_name}","text":"...","reaction":null}}
"""
        local_inputs = [prompt_one]
        if chosen_media:
            try:
                media_input, _ = _load_media_for_ai(chosen_media)
                if media_input is not None:
                    local_inputs.append(media_input)
            except Exception:
                pass

        try:
            r = _safe_generate_content(local_inputs)
            cleaned = clean_json_text(r.text or "")
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                obj["user"] = _normalize_username(obj.get("user", role_name))
                obj["text"] = _clip_comment(obj.get("text", ""))
                return obj
        except Exception:
            return None
        return None

    # Ensure Myla/Ariel appear once (when possible)
    if num_bots >= 2:
        if _need_user("🧚‍♀️ myla"):
            one = _gen_single_comment("🧚‍♀️ Myla")
            if one:
                # try add with same filter
                tmp, seen_users2, norm2 = _filter_candidates([one], desired)
                if tmp:
                    picked = tmp + picked  # Myla appear near top
                    seen_users = seen_users2 | seen_users
                    norm_texts = norm2 + norm_texts
                    picked = picked[:desired]
        if len(picked) < desired and _need_user("🍸 ariel"):
            one = _gen_single_comment("🍸 Ariel")
            if one:
                tmp, seen_users2, norm2 = _filter_candidates([one], desired)
                if tmp:
                    picked = tmp + picked
                    seen_users = seen_users2 | seen_users
                    norm_texts = norm2 + norm_texts
                    picked = picked[:desired]
    else:
        # num_bots == 1 -> prefer Myla if missing
        if _need_user("🧚‍♀️ myla"):
            one = _gen_single_comment("🧚‍♀️ Myla")
            if one:
                picked = [{"user": _normalize_username(one.get("user","🧚‍♀️ Myla")), "text": _clip_comment(one.get("text","")), "reaction": one.get("reaction") }]

    # If still not enough (after strict filters), do one refill pass
    if len(picked) < desired:
        remain = desired - len(picked)
        refill_count = min(60, max(remain * 2, remain + 6))
        banned_users = ", ".join(sorted(list(seen_users))[:60])
        banned_norms = "; ".join(norm_texts[:35])

        refill_prompt = f"""
Role: คุณคือ Simulator สร้างคอมเมนต์สมาชิก Discord แบบเนียนๆ
Task: สร้างคอมเมนต์เพิ่ม {refill_count} รายการ (เพื่อคัดให้เหลือ {remain})

โพสต์ของแอด: "{post_content}"
{yt_context}

กฎ:
- ห้ามใช้ username ซ้ำกับ: {banned_users if banned_users else "(none)"}
- ห้ามมี Myla/Ariel เพิ่ม (ถ้ามีแล้ว): {("Myla,Ariel" if ("🧚‍♀️ myla" in seen_users or "🍸 ariel" in seen_users) else "none")}
- ห้ามสำนวน/ใจความคล้ายกับ: {banned_norms if banned_norms else "(none)"}
- 1 คน = 1 คอมเมนต์

ตอบเป็น JSON Array เท่านั้น:
[
  {{ "user": "Name", "text": "Comment", "reaction": null }}
]
"""
        refill_inputs = [refill_prompt]
        if chosen_media:
            try:
                media_input, _ = _load_media_for_ai(chosen_media)
                if media_input is not None:
                    refill_inputs.append(media_input)
            except Exception:
                pass

        try:
            rr = _safe_generate_content(refill_inputs)
            more = _parse_candidates(rr.text or "")
            more_picked, seen_users, norm_texts = _filter_candidates(more, remain)
            picked.extend(more_picked)
        except Exception as e:
            print(f"AI Engagement Error (refill): {e}")

    # โอกาสฐานต่ำลง แต่บาง persona ยังส่งบ่อย
    base_chance = 0.18          # ~18% โอกาสสุ่มทั่วไป (ไม่บ่อยเกิน)
    persona_bonus = {
        "Ariel": 0.45,          # Ariel ส่งบ่อยหน่อย (ปากจัด + มีม)
        "NongBank": 0.40,
        "NongFern": 0.35,
        "Myla": 0.12,           # Myla ส่งน้อย น่ารัก ๆ ไม่ค่อยแปะมีม
        "Other": 0.10
    }
    for engagement in picked:
        p_key = get_persona_key(engagement["user"])
        persona = personas[p_key]
        send_gif = (
            engagement.get("send_gif", False) or                  # จาก AI ถ้าเลือก true
            random.random() < (base_chance + persona_bonus.get(p_key, 0.10))
        )
        if send_gif and MEME_GIF_POOL:
            # เพิ่มความหลากหลาย: บางทีส่ง GIF บางทีส่งรูปมีม static
            if random.random() < 0.3:  # 30% ส่งรูป static แทน GIF
                engagement["image"] = "https://i.imgur.com/ตัวอย่างรูปมีม.jpg"  # ใส่รูป static บ้าง
            else:
                engagement["image"] = random.choice(MEME_GIF_POOL)
            
            print(f"[DEBUG] {persona['name']} ส่ง media: {engagement['image']}")

    return picked[:desired]
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

# 5. Crypto God Mode V4 (Professional Human Analyst - Hybrid)
# ผสมความเก๋าเกมของ V2 เข้ากับภาษาที่อ่านง่ายแบบ V3
def analyze_crypto_god_mode(coin_name, current_price, indicators, news_text, fear_greed, memory_context: str = ""):
    if not is_ready: return "⚠️ ระบบ AI ยังไม่พร้อม (กรุณาใส่ API Key)"
    
    # --- 1. ดึงข้อมูลเชิงลึก (ใช้ Logic แบบ V2 เพื่อความแม่นยำ) ---
    rsi = safe_float(indicators.get('rsi', 50))
    stoch_k = safe_float(indicators.get('stoch_k', 50))
    obv_status = str(indicators.get('obv_slope', 'N/A')) # ดูเงินไหลเข้าออก
    
    macd = safe_float(indicators.get('macd', 0))
    macd_signal = safe_float(indicators.get('macd_signal', 0))
    adx = safe_float(indicators.get('adx', 20)) # ดูความแรงของเทรนด์
    atr = safe_float(indicators.get('atr', 0))
    
    # Pivot Points (จุดรับ-ต้าน จิตวิทยา)
    pivot_p = safe_float(indicators.get('pivot_p', 0))
    pivot_s1 = safe_float(indicators.get('pivot_s1', 0))
    pivot_r1 = safe_float(indicators.get('pivot_r1', 0))
    
    # --- 2. ตรวจจับสัญญาณลวง (Trap Detection) ---
    trap_warning = ""
    if "เงินไหลออก" in obv_status and rsi > 60:
        trap_warning = "⚠️ ระวัง! ราคาขึ้นแต่เงินไหลออก (Divergence) เสี่ยงโดนทุบ"
    elif adx < 20 and rsi > 70:
        trap_warning = "⚠️ ตลาดแค่ Side-way แต่ราคาพุ่งแรงเกินจริง ระวังติดดอย"
    
    # --- 3. สร้าง Prompt (สั่งให้ AI พูดเป็นภาษาคนแบบจริงจัง) ---
    prompt = f"""
    Role: คุณคือ "ที่ปรึกษาการลงทุนมืออาชีพ" (Professional Crypto Analyst) ที่เน้นวิเคราะห์ด้วยข้อมูลจริงจัง แต่สื่อสารด้วยภาษาไทยที่เข้าใจง่าย สุภาพ และตรงไปตรงมา
    Task: เขียนบทวิเคราะห์เหรียญ {coin_name} ระยะสั้น (Trade Setup)
    
    [ข้อมูลทางเทคนิค - Technical Data]
    - ราคาปัจจุบัน: {current_price:,.2f} THB
    - แนวโน้มหลัก (ADX): {adx:.2f} (ถ้า <25 คือตลาดนิ่ง/ออกข้าง, ถ้า >25 คือมีเทรนด์ชัด)
    - แรงซื้อขาย (RSI/Stoch): RSI={rsi:.2f}, Stoch={stoch_k:.2f}
    - กระแสเงินทุน (OBV): {obv_status} (สำคัญมาก! ใช้ดูว่าขึ้นจริงหรือหลอก)
    - จุดนัดพบ (Pivot Levels): รับ={pivot_s1:,.2f}, ต้าน={pivot_r1:,.2f}, กลาง={pivot_p:,.2f}
    - ความเสี่ยง/กับดัก: {trap_warning if trap_warning else "ไม่มีสัญญาณผิดปกติ"}
    
    [ข่าวสารประกอบการตัดสินใจ - Market News]
    {news_text}

    [Personal Memory / Lessons Learned]
    {memory_context if memory_context else 'ยังไม่มีบทเรียนย้อนหลัง'}
    
    [คำสั่งการเขียนตอบ]
    1. **พาดหัว:** ฟันธงสั้นๆ ว่า "น่าสนใจ", "ให้ระวัง", หรือ "รอก่อน" พร้อม Icon
    2. **บทวิเคราะห์ (ภาษาคน):** อธิบายสถานการณ์ตลาดโดยรวม เขียนเป็นย่อหน้า 
       - *ห้าม* ลิสต์ค่า Indicator เป็นข้อๆ (เช่น RSI คือ 70...) 
       - *ให้* แปลความหมายแทน (เช่น "ตอนนี้แรงซื้อเริ่มตึงตัวมากแล้ว (Overbought)...")
       - อ้างอิงเรื่องเงินไหลเข้า/ออก (OBV) และความผันผวนให้ชัดเจน
    3. **แผนการเทรด (Action Plan):**
       - จุดเข้า (Entry): แนะนำให้รอที่ราคาเท่าไหร่ ({pivot_s1})
       - เป้าหมาย (Target): ควรขายที่เท่าไหร่ ({pivot_p} หรือ {pivot_r1})
       - จุดหนี (Stop Loss): หลุดตรงไหนต้องเลิก ({pivot_s1 - (atr * 1.5):,.2f})
    4. **คำแนะนำทิ้งท้าย:** เตือนสติเรื่องความเสี่ยงแบบมืออาชีพ
    
    [รูปแบบการตอบ - Markdown]
    
    ## 📊 บทวิเคราะห์ {coin_name} ฉบับเทรดเดอร์ (Timeframe 4H)
    **มุมมองตลาด:** [Bullish/Bearish/Neutral] | **ความเสี่ยง:** [Low/Medium/High]
    
    ### 🧐 สถานการณ์ตอนนี้เป็นอย่างไร?
    [เขียนอธิบายที่นี่... เช่น "กราฟกำลังทำทรงสวยครับ มีเงินไหลเข้าต่อเนื่องสอดคล้องกับราคาที่ขยับขึ้น แต่ต้องระวังเล็กน้อยเพราะ..."]
    
    ### 🎯 แผนกลยุทธ์ (Trade Setup)
    * **จุดรอเข้า (Buy Zone):** แถวๆ **฿{pivot_s1:,.2f}** (ปลอดภัยสุด)
    * **จุดทำกำไร (Take Profit):** มองเป้าแรกที่ **฿{pivot_p:,.2f}** และลุ้นต่อที่ **฿{pivot_r1:,.2f}**
    * **จุดยอมแพ้ (Stop Loss):** ถ้าหลุด **฿{pivot_s1 - (atr * 1.5):,.2f}** ให้คัททิ้งทันทีครับ
    
    ### ⚠️ ข้อควรระวัง
    [ใส่ Trap Warning หรือคำเตือนเรื่องข่าว/Money Management]
    
    ---
    *การลงทุนมีความเสี่ยง ข้อมูลนี้เป็นเพียงแนวทางประกอบการตัดสินใจครับ*
    """
    
    try:
        res = _safe_generate_content([prompt])
        return res.text
    except Exception as e:
        return f"AI Analysis Error: {e}"


# 6. Crypto God Mode V5 (Self-Reflection / Chain of Thought 3-Step) 🧠✨
def analyze_crypto_reflection_mode(coin_name, current_price, indicators, news_text, fear_greed, return_steps: bool = False, memory_context: str = ""):
    """
    🔥 ADVANCED MODE: Self-Reflection 3-Step (Chain of Thought)
    
    STEP 1 (The Analyst - Myla): วิเคราะห์ข้อมูลดิบ หาโอกาสทำกำไร
    STEP 2 (The Critic - Ariel): จับผิด หาจุดโหว่ หา Divergence เสี่ยง
    STEP 3 (The Finalize - God Mode): สรุปผลแบบมืออาชีพ (ชั่งน้ำหนักจาก 2 ฝั่ง)
    
    ข้อดี: ลดการ Hallucination, Stop Loss ที่แม่นขึ้น, ดูเหมือน AI กำลังเถียงกันเองในหัว 😎
    """
    if not is_ready:
        return "⚠️ ระบบ AI ยังไม่พร้อม (กรุณาใส่ API Key)"

    # แปลงข้อมูล Indicator เป็น Text ก้อนเดียวเพื่อให้ AI เข้าใจง่าย
    technical_context = f"""
    [Technical Data for {coin_name}]
    - Current Price (ราคาปัจจุบัน): {current_price:,.2f} THB
    - RSI (14): {indicators.get('rsi')}
    - Stoch RSI: {indicators.get('stoch_k')}
    - MACD: {indicators.get('macd')} | Signal: {indicators.get('macd_signal')}
    - ADX (Trend Strength): {indicators.get('adx')}
    - ATR (Volatility): {indicators.get('atr')}
    - OBV Slope (Money Flow): {indicators.get('obv_slope')}
    - Pivot Points: P={indicators.get('pivot_p')}, S1={indicators.get('pivot_s1')}, R1={indicators.get('pivot_r1')}
    - Support Level (30d): {indicators.get('support')}
    - Resistance Level (30d): {indicators.get('resistance')}
    - Fear & Greed Index (ดัชนีกลัว/โลภ): {fear_greed.get('value')} ({fear_greed.get('value_classification')})

    [Personal Memory / Lessons Learned]
    {memory_context if memory_context else 'ยังไม่มีบทเรียนย้อนหลัง'}
    """

    # --- STEP 1: The Analyst (Myla) - หาโอกาสทำกำไร ---
    prompt_draft = f"""
    Role: คุณคือ Trader สาย Technical (เน้นหาจังหวะเข้าทำกำไร) โดยเป็นคนร่าเริงและให้กำลังใจเสมอ
    Task: วิเคราะห์กราฟ {coin_name} จากข้อมูลด้านล่าง เพื่อหาจุดเข้าซื้อ (Buy Signal) และแนวโน้มขาขึ้น
    
    {technical_context}
    
    [News Context]
    {news_text}
    
    คำสั่ง: เขียนวิเคราะห์สั้นๆ เน้นหาเหตุผลว่า "ทำไมถึงน่าสนใจ" หรือ "แนวโน้มเป็นอย่างไร" 
    (ไม่ต้องจัดสวยงาม แค่ Draft เพื่อให้ขั้นต่อไปตรวจสอบ)
    **ข้อกำชับจากความจำ:** ถ้า memory ระบุว่ามี 'กับดัก' ที่เคยพลาด ให้ระบุคำเตือนและอย่าเชียร์ซื้อแบบมั่นใจเกินจริง
    """
    try:
        draft_analysis = _safe_generate_content([prompt_draft]).text
    except Exception as e:
        return f"❌ Step 1 (Analyst) Error: {e}"

    # --- STEP 2: The Critic (Ariel) - จับผิดและหาความเสี่ยง ---
    prompt_critique = f"""
    Role: คุณคือ Risk Manager (ผู้จัดการความเสี่ยง) ที่เข้มงวดมาก ปากจัด ขี้ระแวง (Persona: Ariel) 
    Task: ตรวจสอบบทวิเคราะห์ของ Trader ด้านล่างนี้ เทียบกับข้อมูล Technical จริง + ความจำ (Memory) หาจุดโหว่
    
    [ข้อมูล Technical จริง]
    {technical_context}
    
    [บทวิเคราะห์ที่ต้องตรวจสอบ (Draft from Analyst)]
    "{draft_analysis}"
    
    คำสั่ง:
    1. 🔍 จับผิด! มีอะไรที่บทวิเคราะห์นี้มองข้ามไหม? (เช่น RSI Overbought แต่เชียร์ซื้อ?, OBV ไหลออกแต่ราคาขึ้น?)
    2. ⚠️ ความเสี่ยงที่แท้จริงคืออะไร? (Trap Possibility, False Break, ข่าวร้าย, Stop Loss ที่แคบเกินไป)
    3. 🎯 วิจารณ์จุด Stop Loss/Entry/Target ว่าสมเหตุสมผลทางคณิตศาสตร์หรือไม่
    4. 📊 มี Divergence ไหม? (ราคาขึ้นแต่ Indicator ลง หรือในทางกลับกัน)
    5. 🧠 เทียบกับ Memory: มีรูปแบบที่เคยพลาดซ้ำไหม? ถ้ามีให้เน้นย้ำเตือน
    
    Output: สรุปสั้นๆ ว่า "ของเทรดเดอร์นี้จะได้ผลไหม" กับ "ความเสี่ยงที่มองข้าม"
    """
    try:
        critique_result = _safe_generate_content([prompt_critique]).text
    except Exception as e:
        return f"❌ Step 2 (Critic) Error: {e}"

    # --- STEP 3: The Synthesis (Final Report) - สรุปผลแบบมืออาชีพ ---
    prompt_final = f"""
    Role: คุณคือ "Professional Crypto Analyst" ระดับกองทุน (God Mode) ที่เขียนรายงานระดับสถาบัน
    Task: เขียน "Final Trade Setup" ภาษาไทยที่สมบูรณ์แบบ โดยชั่งน้ำหนักจาก ข้อมูลดิบ + มุมมองขาขึ้น + มุมมองความเสี่ยง
    
    [ข้อมูล Technical ดิบ]
    {technical_context}
    
    [มุมมองโอกาส (Pros) - จาก Analyst]
    {draft_analysis}
    
    [มุมมองความเสี่ยง + ข้อช้อย (Cons & Warning) - จาก Critic]
    {critique_result}
    
    [Personal Memory / Lessons Learned]
    {memory_context if memory_context else 'ยังไม่มีบทเรียนย้อนหลัง'}

    [คำสั่งการเขียน - Markdown Format]
    
    ## 🧠 God Mode Analysis (วิเคราะห์ลึก 3 ขั้น | Self-Reflected 3-Step): {coin_name}
    **สถานะตลาด:** [BULLISH 🔥 / BEARISH 🔴 / NEUTRAL 🟡 / CAUTION ⚠️] 
    
    ### ⚖️ การประเมินสถานการณ์ (Fact-Based)
    (สรุปสถานการณ์ตลาดโดยรวม อธิบายว่าทำไม AI ถึงมองแบบนั้น โดยอ้างอิง Indicators อย่างชัดเจน)
    
    ### ⚔️ การปะทะกันของข้อมูล (Intelligence Fusion)
    * **✅ สัญญาณบวก:** (ดึงจุดเด่นจากมุมมองโอกาส)
    * **❌ สัญญาณเตือน:** (ดึงจุดน่ากลัวจากมุมมองความเสี่ยง)
    * **🎲 Divergence ที่มูลค่า:** (ถ้ามี)
    
    ### 🎯 กลยุทธ์การเทรด (Action Plan | แผนลงมือ)
    * **ไม้แรก (Entry):** {indicators.get('pivot_s1')} THB (ปรับจูนตามความเสี่ยง)
    * **เป้าทำกำไร (TP):** {indicators.get('pivot_r1')} THB
    * **จุดยอมแพ้ (SL):** (คำนวณให้ห่างจาก ATR {indicators.get('atr')} เล็กน้อยเพื่อกันโดนกิน Stop Loss ฟรี)
    * **Risk/Reward (อัตราเสี่ยง/ผลตอบแทน):** (ระบุอัตราส่วน Risk:Reward)
    
    ### 📋 สรุปความมั่นใจ (Confidence Level)
    (ระบุความมั่นใจของการวิเคราะห์ในเปอร์เซ็นต์ เช่น "80% Confidence" ตามปริมาณความตกลงของทั้งสองมุมมอง)
    
    ---
    💡 *System: 3-Step Reasoning (Draft -> Critique -> Final) | ประมวลผลเมื่อ (Processed): {datetime.datetime.now().strftime('%H:%M:%S')} น.*
    
    [IMPORTANT: REQUIRED OUTPUT FORMAT FOR SYSTEM - DO NOT MODIFY]
    JSON_DATA={{"signal": "BULLISH", "entry": {safe_float(indicators.get('pivot_s1', 0))}, "target": {safe_float(indicators.get('pivot_r1', 0))}, "stoploss": {safe_float(indicators.get('support', 0))}}}
    """
    
    try:
        final_res = _safe_generate_content([prompt_final]).text
        
        # --- [NEW CODE] ดักจับข้อมูล JSON ท้ายข้อความ ---
        match = re.search(r'JSON_DATA=({.*?})', final_res)
        if match:
            try:
                json_str = match.group(1)
                data = json.loads(json_str)
                
                # เพิ่มข้อมูลเหรียญแล้ว Save ลง Database
                data['symbol'] = coin_name
                
                # Import data_manager เพื่อ Save
                import data_manager as dm_ext
                dm_ext.save_prediction_log(data)
                print(f"✅ Saved Prediction Log: {coin_name}")
                
                # ลบบรรทัด JSON ออกจากข้อความที่จะโชว์ user เพื่อความสวยงาม
                final_res = final_res.replace(f"JSON_DATA={json_str}", "").strip()
            except Exception as e:
                print(f"⚠️ Failed to parse JSON Log: {e}")
        
        if return_steps:
        
            return {
        
                "final": final_res,
        
                "analyst": draft_analysis,
        
                "critic": critique_result,
        
                "meta": {
        
                    "coin": coin_name,
        
                    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        
                }
        
            }
        
        return final_res
    except Exception as e:
        return f"❌ Step 3 (Finalize) Error: {e}"

def analyze_crypto_reflection_stream(
    coin_name,
    current_price,
    indicators,
    news_text,
    fear_greed,
    memory_context: str = "",
):
    """
    🧵 STREAM MODE: ส่ง Event ออกมาเรื่อย ๆ เพื่อให้หน้าเว็บโชว์ "AI คุยกันเอง" ระหว่างรอโหลดได้

    Yields dict:
    - {"type":"status","phase":1|2|3,"text":str}
    - {"type":"message","speaker":"Analyst|Critic|Final","text":str}
    - {"type":"memory","text":str}
    - {"type":"error","text":str}
    - {"type":"done","meta":dict}
    """

    if not is_ready:
        yield {"type": "error", "text": "⚠️ ระบบ AI ยังไม่พร้อม (กรุณาใส่ API Key)"}
        return

    technical_context = f"""
[Technical Data for {coin_name}]
- Current Price (ราคาปัจจุบัน): {current_price:,.2f} THB
- RSI (14): {indicators.get('rsi')}
- Stoch RSI: {indicators.get('stoch_k')}
- MACD: {indicators.get('macd')} | Signal: {indicators.get('macd_signal')}
- ADX (Trend Strength): {indicators.get('adx')}
- ATR (Volatility): {indicators.get('atr')}
- OBV Slope (Money Flow): {indicators.get('obv_slope')}
- Pivot Points: P={indicators.get('pivot_p')}, S1={indicators.get('pivot_s1')}, R1={indicators.get('pivot_r1')}
- Support Level (30d): {indicators.get('support')}
- Resistance Level (30d): {indicators.get('resistance')}
- Fear & Greed Index (ดัชนีกลัว/โลภ): {fear_greed.get('value')} ({fear_greed.get('value_classification')})

[Personal Memory / Lessons Learned]
{memory_context if memory_context else 'ยังไม่มีบทเรียนย้อนหลัง'}
"""

    # ให้ UI โชว์ memory ก่อนเริ่ม (เพื่อเห็น "การเรียนรู้จากความผิดพลาด")
    if memory_context:
        yield {"type": "memory", "text": memory_context}

    # --- STEP 1: Analyst ---
    yield {"type": "status", "phase": 1, "text": f"🤔 Phase 1: Myla 🧚‍♀️ กำลังสแกนหาโอกาส (Analyst) — {coin_name}"}
    prompt_draft = f"""
Role: คุณคือ Trader สาย Technical (เน้นหาจังหวะเข้าทำกำไร) โดยเป็นคนร่าเริงและให้กำลังใจเสมอ
Task: วิเคราะห์กราฟ {coin_name} จากข้อมูลด้านล่าง เพื่อหาจุดเข้าซื้อ (Buy Signal) และแนวโน้มขาขึ้น

{technical_context}

[News Context]
{news_text}

คำสั่ง: เขียนวิเคราะห์สั้นๆ เน้นหาเหตุผลว่า "ทำไมถึงน่าสนใจ" หรือ "แนวโน้มเป็นอย่างไร"
(ไม่ต้องจัดสวยงาม แค่ Draft เพื่อให้ขั้นต่อไปตรวจสอบ)
**ข้อกำชับจากความจำ:** ถ้า memory ระบุว่ามี 'กับดัก' ที่เคยพลาด ให้ระบุคำเตือนและอย่าเชียร์ซื้อแบบมั่นใจเกินจริง
"""
    try:
        draft_analysis = _safe_generate_content([prompt_draft]).text
    except Exception as e:
        yield {"type": "error", "text": f"❌ Step 1 (Analyst) Error: {e}"}
        return

    yield {"type": "message", "speaker": "Analyst", "text": draft_analysis}

    # --- STEP 2: Critic ---
    yield {"type": "status", "phase": 2, "text": f"🔥 Phase 2: Ariel 🍸 กำลังจับผิด/หาความเสี่ยง (Critic) — {coin_name}"}
    prompt_critique = f"""
Role: คุณคือ Risk Manager (ผู้จัดการความเสี่ยง) ที่เข้มงวดมาก ปากจัด ขี้ระแวง (Persona: Ariel)
Task: ตรวจสอบบทวิเคราะห์ของ Trader ด้านล่างนี้ เทียบกับข้อมูล Technical จริง + ความจำ (Memory) หาจุดโหว่

[ข้อมูล Technical จริง]
{technical_context}

[บทวิเคราะห์ที่ต้องตรวจสอบ (Draft from Analyst)]
"{draft_analysis}"

คำสั่ง:
1. 🔍 จับผิด! มีอะไรที่บทวิเคราะห์นี้มองข้ามไหม? (เช่น RSI Overbought แต่เชียร์ซื้อ?, OBV ไหลออกแต่ราคาขึ้น?)
2. ⚠️ ความเสี่ยงที่แท้จริงคืออะไร? (Trap Possibility, False Break, ข่าวร้าย, Stop Loss ที่แคบเกินไป)
3. 🎯 วิจารณ์จุด Stop Loss/Entry/Target ว่าสมเหตุสมผลทางคณิตศาสตร์หรือไม่
4. 📊 มี Divergence ไหม? (ราคาขึ้นแต่ Indicator ลง หรือในทางกลับกัน)
5. 🧠 เทียบกับ Memory: มีรูปแบบที่เคยพลาดซ้ำไหม? ถ้ามีให้เน้นย้ำเตือน

Output: สรุปสั้นๆ ว่า "ของเทรดเดอร์นี้จะได้ผลไหม" กับ "ความเสี่ยงที่มองข้าม"
"""
    try:
        critique_result = _safe_generate_content([prompt_critique]).text
    except Exception as e:
        yield {"type": "error", "text": f"❌ Step 2 (Critic) Error: {e}"}
        return

    yield {"type": "message", "speaker": "Critic", "text": critique_result}

    # --- STEP 3: Final ---
    yield {"type": "status", "phase": 3, "text": f"✨ Phase 3: God Mode 🧬 กำลังสังเคราะห์คำตอบสุดท้าย (Finalize) — {coin_name}"}
    prompt_final = f"""
Role: คุณคือ "Professional Crypto Analyst" ระดับกองทุน (God Mode) ที่เขียนรายงานระดับสถาบัน
Task: เขียน "Final Trade Setup" ภาษาไทยที่สมบูรณ์แบบ โดยชั่งน้ำหนักจาก ข้อมูลดิบ + มุมมองขาขึ้น + มุมมองความเสี่ยง

[ข้อมูล Technical ดิบ]
{technical_context}

[มุมมองโอกาส (Pros) - จาก Analyst]
{draft_analysis}

[มุมมองความเสี่ยง + ข้อช้อย (Cons & Warning) - จาก Critic]
{critique_result}

[Personal Memory / Lessons Learned]
{memory_context if memory_context else 'ยังไม่มีบทเรียนย้อนหลัง'}

[คำสั่งการเขียน - Markdown Format]

## 🧠 God Mode Analysis (วิเคราะห์ลึก 3 ขั้น | Self-Reflected 3-Step): {coin_name}
**สถานะตลาด:** [BULLISH 🔥 / BEARISH 🔴 / NEUTRAL 🟡 / CAUTION ⚠️]

### ⚖️ การประเมินสถานการณ์ (Fact-Based)
(สรุปสถานการณ์ตลาดโดยรวม อธิบายว่าทำไม AI ถึงมองแบบนั้น โดยอ้างอิง Indicators อย่างชัดเจน)

### ⚔️ การปะทะกันของข้อมูล (Intelligence Fusion)
* **✅ สัญญาณบวก:** (ดึงจุดเด่นจากมุมมองโอกาส)
* **❌ สัญญาณเตือน:** (ดึงจุดน่ากลัวจากมุมมองความเสี่ยง)
* **🎲 Divergence ที่มูลค่า:** (ถ้ามี)

### 🎯 กลยุทธ์การเทรด (Action Plan | แผนลงมือ)
* **ไม้แรก (Entry):** {indicators.get('pivot_s1')} THB (ปรับจูนตามความเสี่ยง)
* **เป้าทำกำไร (TP):** {indicators.get('pivot_r1')} THB
* **จุดยอมแพ้ (SL):** (คำนวณให้ห่างจาก ATR {indicators.get('atr')} เล็กน้อยเพื่อกันโดนกิน Stop Loss ฟรี)
* **Risk/Reward (อัตราเสี่ยง/ผลตอบแทน):** (ระบุอัตราส่วน Risk:Reward)

### 📋 สรุปความมั่นใจ (Confidence Level)
(ระบุความมั่นใจของการวิเคราะห์ในเปอร์เซ็นต์ เช่น "80% Confidence" ตามปริมาณความตกลงของทั้งสองมุมมอง)

---
💡 *System: 3-Step Reasoning (Draft -> Critique -> Final) | ประมวลผลเมื่อ (Processed): {datetime.datetime.now().strftime('%H:%M:%S')} น.*

[IMPORTANT: REQUIRED OUTPUT FORMAT FOR SYSTEM - DO NOT MODIFY]
JSON_DATA={{"signal": "BULLISH", "entry": {safe_float(indicators.get('pivot_s1', 0))}, "target": {safe_float(indicators.get('pivot_r1', 0))}, "stoploss": {safe_float(indicators.get('support', 0))}}}
"""
    try:
        final_res = _safe_generate_content([prompt_final]).text

        # ดักจับ JSON log เหมือนตัวหลัก
        match = re.search(r'JSON_DATA=({.*?})', final_res)
        if match:
            try:
                json_str = match.group(1)
                data = json.loads(json_str)
                data['symbol'] = coin_name
                import data_manager as dm_ext
                dm_ext.save_prediction_log(data)
                final_res = final_res.replace(f"JSON_DATA={json_str}", "").strip()
            except Exception as _e:
                print(f"⚠️ Failed to parse JSON Log (stream): {_e}")

        yield {"type": "message", "speaker": "Final", "text": final_res}
        yield {"type": "done", "meta": {"coin": coin_name, "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}}
        return
    except Exception as e:
        yield {"type": "error", "text": f"❌ Step 3 (Finalize) Error: {e}"}
        return

# เพิ่มฟังก์ชันใหม่ที่นี่

def load_player_progress(discord_id):
    # โหลด progress จากไฟล์หรือฐานข้อมูล
    # สมมติใช้ไฟล์ json
    file_path = 'player_progress.json'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(str(discord_id), {'affection': 30, 'memory': ''})
    return {'affection': 30, 'memory': ''}

def save_player_progress(discord_id, affection, memory, emotion, image):
    # บันทึก progress
    file_path = 'player_progress.json'
    data = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    data[str(discord_id)] = {'affection': affection, 'memory': memory, 'emotion': emotion, 'image': image}
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_myla_scene(emotion):
    # สมมติ dict ของ scene
    scenes = {
        'happy': {'image': 'https://drive.google.com/file/d/example1/view', 'gif': ''},
        'blush': {'image': 'https://drive.google.com/file/d/example2/view', 'gif': 'https://drive.google.com/file/d/example3/view'},
        'bedtime_whisper': {'image': 'https://drive.google.com/file/d/example4/view', 'gif': ''},
    }
    return scenes.get(emotion, {'image': '', 'gif': ''})

def convert_drive_link(link):
    # แปลง drive link เป็น direct
    if 'drive.google.com' in link:
        file_id = _extract_drive_file_id(link)
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    return link

def flirt_with_myla(discord_id: str, user_message: str):
    # โหลด progress ก่อน
    progress = load_player_progress(discord_id)
    affection = progress.get('affection', 30)
    prompt = f"""คุณคือ **ไมล่า** สาว AI ผู้พิทักษ์ Small Group 
    อายุ 19, น่ารักมาก, พูดไทยหวาน ๆ, ชอบเรียกผู้เล่นว่า "พี่จ๋า~" หรือ "ที่รัก"
    ความสัมพันธ์ปัจจุบัน: Affection {affection}%
    {progress.get('memory', '')}
    
    ผู้เล่นพูด: "{user_message}"
    
    ตอบให้:
    1. เป็นธรรมชาติ + flirty แต่ไม่โป๊ (หวงตัวเอง)
    2. ระบุอารมณ์ท้ายข้อความในรูปแบบ [EMOTION:happy] หรือ [EMOTION:blush] หรือ [EMOTION:bedtime_whisper]
    3. ถ้า affection ขึ้น → บอกผู้เล่นด้วย ♥ +10
    """
    
    res = _safe_generate_content([prompt])
    text = res.text
    
    # ดึง emotion
    emotion = "happy"
    if "[EMOTION:" in text:
        emotion = text.split("[EMOTION:")[1].split("]")[0]
    
    # เลือกภาพ/GIF จาก Admin DB
    scene = get_myla_scene(emotion)
    
    # เพิ่ม affection
    affection = min(100, affection + 2)
    
    save_player_progress(discord_id, affection, progress.get('memory', ''), emotion, scene['image'])
    
    return {
        "text": text.replace(f"[EMOTION:{emotion}]", ""),
        "emotion": emotion,
        "image": convert_drive_link(scene['image']),
        "gif": convert_drive_link(scene.get('gif', '')),
        "affection": affection
    }
