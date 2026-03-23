"""
DATA MANAGER - Pure Google Sheets Version
ใช้ gspread + utils.py 100% (ไม่มี JSON)
"""

import streamlit as st
import datetime
import json
import gspread
from utils import (
    _get_gspread_client, 
    _get_crypto_memory_sheet_config
)

# =========================================================
# Config (ใช้ secrets เดียวกับ utils.py)
# =========================================================
def _get_main_sheet_config():
    """ดึง main_sheet_id จาก [google_sheets] เท่านั้น (ตามที่บอสให้มา)"""
    cfg = st.secrets.get("google_sheets", {})
    
    sheet_id = cfg.get("main_sheet_id") or cfg.get("posts_sheet_id")
    
    if not sheet_id:
        # กันกรณี secrets ยังไม่สมบูรณ์ (แต่แนะนำย้ายไป [google_sheets] ให้หมด)
        sheet_id = st.secrets.get("main_sheet_id") or st.secrets.get("posts_sheet_id")
    
    return sheet_id

# =========================================================
# ฟังก์ชันหลักที่ app.py เรียกใช้
# =========================================================

def load_data():
    """โหลดโพสต์ + แปลง JSON อัตโนมัติ (สำคัญมาก!)"""
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id: return []

    try:
        sh = client.open_by_key(sheet_id)
        try:
            ws = sh.worksheet("Posts")
        except gspread.exceptions.WorksheetNotFound: # 👈 เฉพาะหาไม่เจอจริงๆ เท่านั้น
            ws = sh.add_worksheet(title="Posts", rows=1000, cols=20)
            # ใช้ column ตามโครงสร้างเดิมเพื่อไม่ให้ระบบพัง
            ws.append_row(["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"])
            return []
        except Exception as e: # 👈 ดูว่ามันพังเพราะอะไรกันแน่
            st.error(f"Google Sheets API มีปัญหา: {e}")
            return []
            
        records = ws.get_all_records()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return []

    # === แปลงทุกคอลัมน์ที่เป็น JSON string ให้เป็น dict/list ===
    for row in records:
        # reactions
        if isinstance(row.get("reactions"), str) and row["reactions"].strip():
            try:
                row["reactions"] = json.loads(row["reactions"])
            except:
                row["reactions"] = {"😻": row.get("likes", 0), "🙀": 0, "😿": 0, "😾": 0, "🧠": 0}
        else:
            row["reactions"] = {"😻": row.get("likes", 0), "🙀": 0, "😿": 0, "😾": 0, "🧠": 0}

        # images
        if isinstance(row.get("images"), str) and row["images"].strip():
            try:
                row["images"] = json.loads(row["images"])
            except:
                row["images"] = []

        # video
        if isinstance(row.get("video"), str) and row["video"].strip():
            try:
                row["video"] = json.loads(row["video"])
            except:
                row["video"] = []

        # comments
        if isinstance(row.get("comments"), str) and row["comments"].strip():
            try:
                row["comments"] = json.loads(row["comments"])
            except:
                row["comments"] = []

    return records

def save_data(posts_list):
    """บันทึกโพสต์ทั้งหมด"""
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id:
        return

    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Posts")
    except:
        ws = sh.add_worksheet(title="Posts", rows=1000, cols=20)
        ws.append_row(["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"])

    # ล้างข้อมูลเก่า + เขียนใหม่ (เร็วที่สุด)
    ws.clear()
    ws.append_row(["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"])

    for p in posts_list:
        row = [
            p.get("id", ""),
            p.get("date", ""),
            p.get("content", ""),
            json.dumps(p.get("images", [])),
            json.dumps(p.get("video", [])),
            p.get("color", "#A370F7"),
            p.get("price", 0),
            p.get("likes", 0),
            json.dumps(p.get("reactions", {})),
            json.dumps(p.get("comments", []))
        ]
        ws.append_row(row)

# =========================================================
# Profile + Snippets + Mailbox
# =========================================================

def _serialize_for_sheet(value):
    """แปลง dict/list ให้เป็น JSON string อัตโนมัติ (กัน error)"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def save_profile(profile_dict):
    """บันทึก Profile แบบปลอดภัย (รองรับ billboard เป็น dict)"""
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id:
        return

    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Profile")
    except:
        ws = sh.add_worksheet(title="Profile", rows=100, cols=30)
        ws.append_row(list(profile_dict.keys()))  # สร้าง header ครั้งแรก

    # --- ล้าง + เขียนใหม่ (แต่ serialize ก่อน) ---
    ws.clear()

    # Header
    ws.append_row(list(profile_dict.keys()))

    # Values (แปลง dict → JSON string)
    serialized_values = [_serialize_for_sheet(v) for v in profile_dict.values()]
    ws.append_row(serialized_values)

    print("✅ Profile saved successfully (billboard serialized)")


def load_profile():
    """โหลด + แปลง JSON string กลับเป็น dict อัตโนมัติ"""
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id:
        return {"name": "Dearluxion", "emoji": "😎", "status": "ยินดีต้อนรับ"}

    try:
        ws = client.open_by_key(sheet_id).worksheet("Profile")
        records = ws.get_all_records()
        if not records:
            return {}
        
        row = records[0]  # แถวแรกคือข้อมูลโปรไฟล์

        # แปลงทุกคอลัมน์ที่เป็น JSON string กลับเป็น dict/list
        for key in row:
            val = row[key]
            if isinstance(val, str) and val.strip().startswith(('{', '[')):
                try:
                    row[key] = json.loads(val)
                except:
                    pass  # ถ้า parse ไม่ได้ก็เว้นไว้ (string ธรรมดา)

        return row

    except Exception as e:
        print(f"⚠️ Load profile failed: {e}")
        return {"name": "Dearluxion", "emoji": "😎", "status": "ยินดีต้อนรับ"}


def load_snippets():
    # ใช้ worksheet Snippets
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    try:
        ws = client.open_by_key(sheet_id).worksheet("Snippets")
        return ws.get_all_records()
    except:
        return []

def load_mailbox():
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    try:
        ws = client.open_by_key(sheet_id).worksheet("Mailbox")
        return ws.get_all_records()
    except:
        return []

# =========================================================
# Prediction Engine (Backtest)
# =========================================================

def get_pending_predictions():
    client = _get_gspread_client()
    sheet_id, _ = _get_crypto_memory_sheet_config()  # ใช้ sheet เดียวกับ memory
    try:
        ws = client.open_by_key(sheet_id).worksheet("Predictions")
        rows = ws.get_all_records()
        return [r for r in rows if str(r.get("status", "")).upper() == "PENDING"]
    except:
        return []

def update_prediction_result(row_idx, status, score, current_price):
    client = _get_gspread_client()
    sheet_id, _ = _get_crypto_memory_sheet_config()
    try:
        ws = client.open_by_key(sheet_id).worksheet("Predictions")
        # แก้ column ให้ตรงกับ sheet ที่มี status/score/close_price แยกคอลัมน์
        ws.update_cell(row_idx + 2, 9, status)          # I = status
        ws.update_cell(row_idx + 2, 10, score)          # J = score
        ws.update_cell(row_idx + 2, 11, current_price)  # K = close_price
    except Exception as e:
        print(f"Update prediction error: {e}")

def save_prediction_log(data: dict):
    """บันทึก prediction log (ใช้ใน ai_manager)"""
    client = _get_gspread_client()
    sheet_id, _ = _get_crypto_memory_sheet_config()
    try:
        ws = client.open_by_key(sheet_id).worksheet("Predictions")
    except:
        ws = client.open_by_key(sheet_id).add_worksheet("Predictions", 1000, 15)
        ws.append_row(["symbol","signal","entry","target","stoploss","status","score","price","timestamp"])

    row = [
        data.get("symbol"),
        data.get("signal"),
        data.get("entry"),
        data.get("target"),
        data.get("stoploss"),
        data.get("status", "PENDING"),
        data.get("confidence", 50),
        data.get("price"),
        datetime.datetime.now().isoformat()
    ]
    ws.append_row(row)

# =========================================================
# Crypto Cache (optional)
# =========================================================
def update_crypto_cache(symbol, analysis_text):
    # เก็บไว้เผื่อใช้ในอนาคต
    pass  # ถ้าต้องการจริง บอกมาได้เลย

# =========================================================
# TODAY SUMMARY (สำหรับ Crypto Tactical War Room)
# =========================================================
def get_today_summary():
    """สรุปผลการทำนาย + บทเรียนวันนี้ (ใช้ใน War Room)"""
    import datetime
    from utils import fetch_crypto_memory_rows  # 👈 เพิ่มบรรทัดนี้เข้ามาข้างในฟังก์ชัน!

    pending = get_pending_predictions()          # จาก Predictions sheet
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # ดึงบทเรียนย้อนหลังวันนี้ (จาก Crypto_Memory sheet)
    memory_rows = fetch_crypto_memory_rows()     # 👈 ตอนนี้ระบบจะรู้จักและหาเจอแน่นอนครับ
    today_memory = [r for r in memory_rows 
                    if str(r.get("timestamp", "")).startswith(today_str)]
    
    win_today = sum(1 for r in today_memory if str(r.get("outcome", "")).upper() == "WIN")
    total_today = len(today_memory)
    winrate_today = round((win_today / total_today * 100), 1) if total_today > 0 else 0.0
    
    return {
        "date": today_str,
        "pending_predictions": len(pending),
        "today_memory_count": len(today_memory),
        "today_winrate": winrate_today,
        "pending_items": pending[:5],           # 5 อันล่าสุด
        "message": f"วันนี้ ( {today_str} ) มีการทำนายค้างตรวจ {len(pending)} รายการ | Win Rate วันนี้ {winrate_today}%"
    }
