import streamlit as st
import json
from datetime import datetime
import data_manager as dm
from utils import _get_gspread_client, _get_crypto_memory_sheet_config, convert_drive_link

# ==================== GOOGLE SHEETS (แก้ไขเรียบร้อย) ====================
def get_myla_sheet():
    sheet_id, _ = _get_crypto_memory_sheet_config()   # เรียกจาก utils โดยตรง
    worksheet = "Myla_Game_Progress"
    return sheet_id, worksheet

def save_player_progress(discord_id, affection, history, current_emotion, current_image):
    client = _get_gspread_client()   # ← แก้ตรงนี้
    if not client: return
    sheet_id, ws_name = get_myla_sheet()
    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
    except:
        ws = client.open_by_key(sheet_id).add_worksheet(title=ws_name, rows=1000, cols=10)
        ws.append_row(["timestamp", "discord_id", "affection", "history", "emotion", "image"])

    row = [
        datetime.now().isoformat(),
        str(discord_id),
        round(affection, 1),
        json.dumps(history[-50:]),
        current_emotion,
        current_image
    ]
    ws.append_row(row)

def load_player_progress(discord_id):
    client = _get_gspread_client()   # ← แก้ตรงนี้
    if not client:
        return {'affection': 30, 'history': [], 'emotion': 'happy', 'image': ''}
    
    sheet_id, ws_name = get_myla_sheet()
    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
        rows = ws.get_all_records()
        for r in reversed(rows):
            if str(r.get("discord_id", "")) == str(discord_id):
                return {
                    'affection': float(r.get("affection", 30)),
                    'history': json.loads(r.get("history", "[]")),
                    'emotion': r.get("emotion", "happy"),
                    'image': r.get("image", "")
                }
    except:
        pass
    return {'affection': 30, 'history': [], 'emotion': 'happy', 'image': ''}

# ==================== SCENES (6 อารมณ์) ====================
MYLA_SCENES = {
    "happy": {"image": "https://lh3.googleusercontent.com/d/1ABC123...YOUR_LINK_1", "gif": ""},
    "blush": {"image": "https://lh3.googleusercontent.com/d/1GHI789...YOUR_LINK_2", "gif": ""},
    "bedtime_whisper": {"image": "https://lh3.googleusercontent.com/d/1JKL012...YOUR_LINK_3", "gif": ""},
    "excited": {"image": "https://lh3.googleusercontent.com/d/1PQR678...YOUR_LINK_4", "gif": ""},
    "shy": {"image": "https://lh3.googleusercontent.com/d/1STU901...YOUR_LINK_5", "gif": ""},
    "kiss": {"image": "https://lh3.googleusercontent.com/d/1VWX234...YOUR_LINK_6", "gif": ""}
}

def get_myla_scene(emotion):

    """โหลดจากโปรไฟล์ก่อน (Admin แก้ได้) ถ้าไม่มีให้ใช้ค่าเริ่มต้น"""

    try:

        import data_manager as dm

        profile = dm.load_profile()

        dynamic_scenes = profile.get('myla_scenes', MYLA_SCENES)

        return dynamic_scenes.get(emotion, MYLA_SCENES.get("happy", {"image": "", "gif": ""}))

    except:

        return MYLA_SCENES.get(emotion, MYLA_SCENES["happy"])