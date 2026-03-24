import streamlit as st
import json
from datetime import datetime
import data_manager as dm
from utils import _get_gspread_client, _get_crypto_memory_sheet_config, convert_drive_link

# ==================== CONFIG & SETUP ====================
def get_myla_sheet_info():
    sheet_id, _ = _get_crypto_memory_sheet_config()
    return sheet_id

# ==================== SCENE MANAGER (Admin) ====================

@st.cache_data(ttl=600)
def load_myla_scenes():
    """โหลดการตั้งค่าฉากและอารมณ์จาก Google Sheets"""
    client = _get_gspread_client()
    if not client:
        return {}  # Fallback

    sheet_id = get_myla_sheet_info()
    ws_name = "Myla_Scenes_Config"

    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
        data = ws.get_all_records()
        scenes = {r.get('emotion', '').strip(): {'image': r.get('image', ''), 'gif': r.get('gif', '')} for r in data if r.get('emotion')}
        if not scenes:
            raise ValueError('No scene data')
        return scenes
    except Exception:
        return {
            'happy': {'image': '', 'gif': ''},
            'blush': {'image': '', 'gif': ''},
        }


def save_myla_scene_config(emotion, image_url, gif_url):
    """ฟังก์ชันสำหรับ Admin ในการบันทึก/แก้ไขฉาก"""
    client = _get_gspread_client()
    if not client:
        return False

    sheet_id = get_myla_sheet_info()
    ws_name = "Myla_Scenes_Config"

    try:
        try:
            ws = client.open_by_key(sheet_id).worksheet(ws_name)
        except Exception:
            ws = client.open_by_key(sheet_id).add_worksheet(title=ws_name, rows=100, cols=5)
            ws.append_row(["emotion", "image", "gif"])

        cell = ws.find(str(emotion))
        if cell:
            ws.update_cell(cell.row, 2, image_url)
            ws.update_cell(cell.row, 3, gif_url)
        else:
            ws.append_row([emotion, image_url, gif_url])

        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Error saving scene: {e}")
        return False


# ==================== PLAYER PROGRESS (Optimized) ====================

def save_player_progress(discord_id, affection, history, current_emotion, current_image):
    """บันทึกความคืบหน้าแบบ Update แถวเดิม (ไม่เพิ่มแถวใหม่เรื่อยๆ)"""
    client = _get_gspread_client()
    if not client:
        return

    sheet_id = get_myla_sheet_info()
    ws_name = "Myla_Game_Progress"

    try:
        try:
            ws = client.open_by_key(sheet_id).worksheet(ws_name)
        except Exception:
            ws = client.open_by_key(sheet_id).add_worksheet(title=ws_name, rows=1000, cols=10)
            ws.append_row(["discord_id", "affection", "history", "emotion", "image", "last_update"])

        cell = ws.find(str(discord_id))

        row_data = [
            str(discord_id),
            round(affection, 1),
            json.dumps(history[-20:]),
            current_emotion,
            current_image,
            datetime.now().isoformat()
        ]

        if cell:
            cell_range = f'A{cell.row}:F{cell.row}'
            ws.update(cell_range, [row_data])
        else:
            ws.append_row(row_data)

    except Exception as e:
        st.error(f"Save Error: {e}")


def load_player_progress(discord_id):
    """โหลดความคืบหน้าของผู้เล่นจากแถวเดียว (หรือ fallback ค่าเริ่มต้น)"""
    client = _get_gspread_client()
    if not client:
        return {'affection': 30, 'history': [], 'emotion': 'happy', 'image': ''}

    sheet_id = get_myla_sheet_info()
    ws_name = 'Myla_Game_Progress'

    try:
        ws = client.open_by_key(sheet_id).worksheet(ws_name)
        rows = ws.get_all_records()
        for r in rows:
            if str(r.get('discord_id', '')) == str(discord_id):
                try:
                    history = json.loads(r.get('history', '[]'))
                except Exception:
                    history = []
                return {
                    'affection': float(r.get('affection', 30)),
                    'history': history,
                    'emotion': r.get('emotion', 'happy'),
                    'image': r.get('image', '')
                }
    except Exception:
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
    """เลือกฉากจากโปรไฟล์ Admin > Google Sheets > ค่าเริ่มต้น"""
    try:
        profile = dm.load_profile()
        dynamic_scenes = profile.get('myla_scenes', {})
        if emotion in dynamic_scenes:
            return dynamic_scenes.get(emotion)
    except Exception:
        pass

    try:
        scenes = load_myla_scenes()
        if emotion in scenes:
            return scenes.get(emotion)
    except Exception:
        pass

    return MYLA_SCENES.get(emotion, MYLA_SCENES.get('happy', {'image': '', 'gif': ''}))
