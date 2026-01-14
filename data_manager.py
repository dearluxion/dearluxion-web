import streamlit as st
import os
import json
import datetime
import threading

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

# Cache Resource connection to GSheets (เชื่อมต่อครั้งเดียวพอ)
@st.cache_resource
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

# --- LOAD DATA (ปรับ TTL ให้เหมาะสม) ---
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
    # 1. Save local JSON first (Fastest)
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

    # 2. Clear Cache immediately so UI updates
    load_data_cached.clear()

    # 3. Save to Sheets in Background Thread (Don't make user wait)
    def _save_sheet_worker(data_to_save):
        sh = get_gsheet_client()
        if sh:
            try:
                ws = sh.worksheet("posts")
                rows = [["id", "date", "content", "images", "video", "color", "price", "likes", "reactions", "comments"]]
                for p in data_to_save:
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
            except Exception as e:
                print(f"Sheet Save Error: {e}")

    threading.Thread(target=_save_sheet_worker, args=(data,)).start()

# --- PROFILE MANAGER ---
@st.cache_data(ttl=300) # Profile ไม่เปลี่ยนบ่อย Cache นานหน่อยได้
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
    # Save Local
    try:
        with open(PROFILE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass
    
    # Clear Cache
    load_profile.clear()
    
    # Background Save
    def _save_pf_worker(data_to_save):
        sh = get_gsheet_client()
        if sh:
            try:
                ws = sh.worksheet("profile")
                rows = [["key", "value"]]
                for k,v in data_to_save.items():
                    val = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    rows.append([k, val])
                ws.clear()
                ws.update(rows)
            except: pass
    threading.Thread(target=_save_pf_worker, args=(data,)).start()

# --- MAILBOX MANAGER ---
def load_mailbox():
    # Mailbox doesn't need heavy caching, user checks occasionally
    if not os.path.exists(MAILBOX_FILE): return []
    try:
        with open(MAILBOX_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_mailbox(data):
    # Save Local
    try:
        with open(MAILBOX_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass
    
    # Background Save
    def _save_mail_worker(data_to_save):
        sh = get_gsheet_client()
        if sh:
            try:
                ws = sh.worksheet("mailbox")
                rows = [["date", "text"]]
                for m in data_to_save: rows.append([m['date'], m['text']])
                ws.clear()
                ws.update(rows)
            except: pass
    threading.Thread(target=_save_mail_worker, args=(data,)).start()

# --- SPECIAL NOTES MANAGER ---
def save_special_note_to_sheet(note_text):
    # อันนี้ Admin ใช้ นานๆ ที รอได้
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
        try: return sh.worksheet("admin_notes").get_all_records()
        except: return []
    return []