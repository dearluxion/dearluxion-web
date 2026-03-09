import streamlit as st
import json
from datetime import datetime
import data_manager as dm
import ai_manager as ai
from utils import convert_drive_link

# ==================== GOOGLE SHEETS ====================
def get_myla_sheet():
    sheet_id = dm._get_crypto_memory_sheet_config()[0]  # ใช้ sheet เดียวกับที่มีอยู่
    worksheet = "Myla_Game_Progress"
    return sheet_id, worksheet

def save_player_progress(discord_id, affection, history, current_emotion, current_image):
    client = dm._get_gspread_client()
    if not client:
        return
    sheet_id, ws_name = get_myla_sheet()
    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
    except:
        ws = client.open_by_key(sheet_id).add_worksheet(title=ws_name, rows=1000, cols=10)
    
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
    client = dm._get_gspread_client()
    if not client:
        return {'affection': 30, 'history': [], 'emotion': 'happy', 'image': ''}
    
    sheet_id, ws_name = get_myla_sheet()
    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
        rows = ws.get_all_records()
        for r in reversed(rows):
            if str(r.get('discord_id', '')) == str(discord_id):
                return {
                    'affection': float(r.get('affection', 30)),
                    'history': json.loads(r.get('history', '[]')),
                    'emotion': r.get('emotion', 'happy'),
                    'image': r.get('image', '')
                }
    except:
        pass
    return {'affection': 30, 'history': [], 'emotion': 'happy', 'image': ''}

# ==================== SCENES (6 อารมณ์) ====================
MYLA_SCENES = {
    "happy": {
        "image": "https://lh3.googleusercontent.com/d/1ABC123...YOUR_LINK_1",  # ← เปลี่ยนเป็น Drive Link ของพี่
        "gif": "https://lh3.googleusercontent.com/d/1DEF456...YOUR_GIF_1"
    },
    "blush": {
        "image": "https://lh3.googleusercontent.com/d/1GHI789...YOUR_LINK_2",
        "gif": ""
    },
    "bedtime_whisper": {
        "image": "https://lh3.googleusercontent.com/d/1JKL012...YOUR_LINK_3",
        "gif": "https://lh3.googleusercontent.com/d/1MNO345...YOUR_GIF_3"
    },
    "excited": {
        "image": "https://lh3.googleusercontent.com/d/1PQR678...YOUR_LINK_4",
        "gif": ""
    },
    "shy": {
        "image": "https://lh3.googleusercontent.com/d/1STU901...YOUR_LINK_5",
        "gif": ""
    },
    "kiss": {
        "image": "https://lh3.googleusercontent.com/d/1VWX234...YOUR_LINK_6",
        "gif": "https://lh3.googleusercontent.com/d/1YZA567...YOUR_GIF_6"
    }
}

def get_myla_scene(emotion):
    return MYLA_SCENES.get(emotion, MYLA_SCENES["happy"])