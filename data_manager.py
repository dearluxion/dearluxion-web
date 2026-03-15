import json
import os
import datetime

# ==========================================
# File Paths (กำหนดชื่อไฟล์ฐานข้อมูล JSON)
# ==========================================
DATA_FILE = "posts.json"
PROFILE_FILE = "profile.json"
SNIPPETS_FILE = "snippets.json"
MAILBOX_FILE = "mailbox.json"
CRYPTO_CACHE_FILE = "crypto_cache.json"
SUMMARY_FILE = "daily_summary.json"
PREDICTIONS_FILE = "predictions.json"

# ==========================================
# Helper Functions (ตัวช่วยอ่าน/เขียน JSON)
# ==========================================
def _load_json(file_path, default_value):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_value
    return default_value

def _save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 📝 ระบบ Posts / ร้านค้า
# ==========================================
def load_data():
    return _load_json(DATA_FILE, [])

def save_data(data):
    _save_json(DATA_FILE, data)

# ==========================================
# 👤 ระบบ Profile / ตั้งค่า Myla Game
# ==========================================
def load_profile():
    return _load_json(PROFILE_FILE, {})

def save_profile(data):
    _save_json(PROFILE_FILE, data)

# ==========================================
# 💻 ระบบ Code Snippets
# ==========================================
def load_snippets():
    return _load_json(SNIPPETS_FILE, [])

def save_snippets(data):
    _save_json(SNIPPETS_FILE, data)

# ==========================================
# 💌 ระบบ Mailbox (จดหมายลับ)
# ==========================================
def load_mailbox():
    return _load_json(MAILBOX_FILE, [])

def save_mailbox(data):
    _save_json(MAILBOX_FILE, data)

# ==========================================
# 📈 ระบบ Crypto Cache (ลดการใช้ API)
# ==========================================
def get_crypto_cache(symbol):
    cache = _load_json(CRYPTO_CACHE_FILE, {})
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    if symbol in cache:
        data = cache[symbol]
        # คืนค่าแคชเฉพาะของวันนี้เท่านั้น
        if data.get('date') == today:
            return data
    return None

def update_crypto_cache(symbol, analysis_result):
    cache = _load_json(CRYPTO_CACHE_FILE, {})
    now = datetime.datetime.now()
    
    cache[symbol] = {
        "date": now.strftime("%Y-%m-%d"),
        "updated_at": now.strftime("%H:%M"),
        "analysis": analysis_result
    }
    _save_json(CRYPTO_CACHE_FILE, cache)

# ==========================================
# ⚖️ ระบบ Crypto Backtest / Predictions
# ==========================================
def get_today_summary():
    return _load_json(SUMMARY_FILE, [])
    
def get_pending_predictions():
    return _load_json(PREDICTIONS_FILE, [])
    
def save_prediction_log(data):
    predictions = _load_json(PREDICTIONS_FILE, [])
    predictions.append(data)
    _save_json(PREDICTIONS_FILE, predictions)