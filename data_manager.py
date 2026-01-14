import streamlit as st
import os
import json
import datetime
import time

# --- ส่วนเสริมสำหรับ Google Sheets ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
    has_gspread = True
except ImportError:
    has_gspread = False

DB_FILE = "portfolio_db.json"
PROFILE_FILE = "profile_db.json"
MAILBOX_FILE = "mailbox_db.json"

# ฟังก์ชันเชื่อมต่อ Google Sheets
def get_gsheet_client():
    if not has_gspread: return None
    if "gcp_service_account" not in st.secrets: return None
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet_name = st.secrets.get("sheet_name", "streamlit_db")
        return client.open(sheet_name)
    except Exception as e:
        return None

# --- LOAD DATA ---
@st.cache_data(ttl=60)
def load_data_cached():
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            records = ws.get_all_records()
            clean_data = []
            for r in records:
                if not str(r['id']): continue
                try:
                    r['images'] = json.loads(r['images']) if r['images'] else []
                    r['video'] = json.loads(r['video']) if r['video'] else []
                    r['reactions'] = json.loads(r['reactions']) if r['reactions'] else {'😻':0,'🙀':0,'😿':0,'😾':0,'🧠':0}
                    r['comments'] = json.loads(r['comments']) if r['comments'] else []
                    clean_data.append(r)
                except: continue
            return clean_data
        except: pass
    
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def load_data():
    return load_data_cached()

# --- SAVE DATA ---
def save_data(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("posts")
            rows = [["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"]]
            for p in data:
                rows.append([
                    str(p.get('id','')), p.get('date',''), p.get('content',''),
                    json.dumps(p.get('images', [])),
                    json.dumps(p.get('video', [])),
                    p.get('color', '#A370F7'), p.get('price', 0), 0,
                    json.dumps(p.get('reactions', {})),
                    json.dumps(p.get('comments', []))
                ])
            ws.clear()
            ws.update(rows)
            load_data_cached.clear()
        except Exception as e:
            st.error(f"บันทึกลง Sheets ไม่สำเร็จ: {e}")

    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
        load_data_cached.clear()
    except: st.error("บันทึกไฟล์สำรองไม่สำเร็จ")

# --- PROFILE MANAGER ---
def load_profile():
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("profile")
            records = ws.get_all_records()
            pf = {}
            for r in records:
                try: val = json.loads(r['value'])
                except: val = r['value']
                pf[r['key']] = val
            return pf
        except: pass
        
    if not os.path.exists(PROFILE_FILE): return {}
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_profile(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("profile")
            rows = [["key", "value"]]
            for k,v in data.items():
                val = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                rows.append([k, val])
            ws.clear()
            ws.update(rows)
        except: pass
        
    try:
        with open(PROFILE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: st.error("บันทึกโปรไฟล์ไม่สำเร็จ")

# --- MAILBOX MANAGER ---
def load_mailbox():
    sh = get_gsheet_client()
    if sh:
        try: return sh.worksheet("mailbox").get_all_records()
        except: pass
        
    if not os.path.exists(MAILBOX_FILE): return []
    try:
        with open(MAILBOX_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_mailbox(data):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("mailbox")
            rows = [["date", "text"]]
            for m in data: rows.append([m['date'], m['text']])
            ws.clear()
            ws.update(rows)
        except: pass
        
    try:
        with open(MAILBOX_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: st.error("ส่งจดหมายไม่สำเร็จ")

# --- SPECIAL NOTES MANAGER (Admin Notes) ---
def save_special_note_to_sheet(note_text):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("admin_notes")
            ws.append_row([datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), note_text])
            return True
        except: return False
    return False

def delete_special_note(row_index):
    sh = get_gsheet_client()
    if sh:
        try:
            ws = sh.worksheet("admin_notes")
            ws.delete_rows(row_index + 2)
            return True
        except: return False
    return False

def load_special_notes():
    sh = get_gsheet_client()
    if sh:
        try:
            return sh.worksheet("admin_notes").get_all_records()
        except: return []
    return []