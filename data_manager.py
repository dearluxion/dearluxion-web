"""
DATA MANAGER - Pure Google Sheets Version
ใช้ gspread + utils.py 100% (ไม่มี JSON)
"""

import streamlit as st
import datetime
import json
from utils import _get_gspread_client, _get_crypto_memory_sheet_config

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
    """โหลดโพสต์ทั้งหมด (Posts worksheet)"""
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id:
        return []

    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet("Posts")
        records = ws.get_all_records()
        return records
    except Exception:
        # ถ้า worksheet ยังไม่มี → สร้างใหม่
        sh = client.open_by_key(sheet_id)
        ws = sh.add_worksheet(title="Posts", rows=1000, cols=20)
        headers = ["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"]
        ws.append_row(headers)
        return []

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

def load_profile():
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id:
        return {"name": "Dearluxion", "emoji": "😎", "status": "ยินดีต้อนรับ"}

    try:
        ws = client.open_by_key(sheet_id).worksheet("Profile")
        data = ws.get_all_records()
        return data[0] if data else {}
    except:
        return {"name": "Dearluxion", "emoji": "😎", "status": "ยินดีต้อนรับ"}

def save_profile(profile_dict):
    client = _get_gspread_client()
    sheet_id = _get_main_sheet_config()
    if not client or not sheet_id:
        return

    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Profile")
    except:
        ws = sh.add_worksheet(title="Profile", rows=100, cols=20)
        ws.append_row(list(profile_dict.keys()))

    # อัปเดตแถวแรก
    ws.clear()
    ws.append_row(list(profile_dict.keys()))
    ws.append_row(list(profile_dict.values()))

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
        ws.update_cell(row_idx + 2, 6, status)      # column F = status
        ws.update_cell(row_idx + 2, 7, score)       # column G = score
        ws.update_cell(row_idx + 2, 8, current_price)
    except:
        pass

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
