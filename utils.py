import re
import requests
import streamlit as st
import urllib.parse
import datetime
import json
import collections
import mimetypes

# =========================================================
# Google Sheets (Crypto Analysis Logger)
# =========================================================

@st.cache_resource(show_spinner=False)
def _get_gspread_client():
    """สร้าง gspread client จาก service account ใน st.secrets

    รองรับหลายรูปแบบ key เพื่อให้เข้ากับโปรเจกต์เดิมได้ง่าย:
    - st.secrets["google_service_account"]
    - st.secrets["gcp_service_account"]
    - st.secrets["service_account"]
    - st.secrets["gspread"]["service_account"]
    (และรองรับกรณีเก็บเป็น JSON string)
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        sa_info = (
            st.secrets.get("google_service_account")
            or st.secrets.get("gcp_service_account")
            or st.secrets.get("service_account")
            or st.secrets.get("gspread", {}).get("service_account")
        )

        if not sa_info:
            return None

        # รองรับกรณีเก็บเป็น JSON string
        if isinstance(sa_info, str):
            sa_info = json.loads(sa_info)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(dict(sa_info), scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Google Sheets client init failed: {e}")
        return None


def _get_crypto_sheet_config():
    """ดึง config ของชีทจาก secrets แบบยืดหยุ่น"""
    cfg = st.secrets.get("google_sheets", {})

    sheet_id = (
        cfg.get("crypto_analysis_sheet_id")
        or cfg.get("crypto_sheet_id")
        or st.secrets.get("crypto_analysis_sheet_id")
        or st.secrets.get("crypto_sheet_id")
    )
    worksheet_name = cfg.get("crypto_analysis_worksheet", "Crypto_Analysis_Log")

    return sheet_id, worksheet_name

# =========================================================
# Google Sheets (Crypto Memory / Lessons Learned)
# =========================================================

def _get_crypto_memory_sheet_config():
    """ดึง config ของชีท Memory จาก secrets แบบยืดหยุ่น

    Priorities:
    1) [google_sheets].crypto_memory_sheet_id / crypto_memory_worksheet
    2) reuse crypto analysis logger sheet id (crypto_analysis_sheet_id)
    3) fallback to homework sheet id (homework_sheet_id) if user uses that
    """
    cfg = st.secrets.get("google_sheets", {})

    sheet_id = (
        cfg.get("crypto_memory_sheet_id")
        or cfg.get("crypto_learning_sheet_id")
        or cfg.get("crypto_analysis_sheet_id")
        or cfg.get("homework_sheet_id")
        or st.secrets.get("crypto_memory_sheet_id")
        or st.secrets.get("crypto_learning_sheet_id")
        or st.secrets.get("crypto_analysis_sheet_id")
        or st.secrets.get("homework_sheet_id")
    )
    worksheet_name = cfg.get("crypto_memory_worksheet") or cfg.get("crypto_learning_worksheet") or "Crypto_Memory"
    return sheet_id, worksheet_name


def append_crypto_memory_to_gsheet(
    *,
    symbol: str,
    outcome: str,
    self_score: int | float,
    mistakes: str,
    fix_plan: str,
    tags: str = "",
    mode: str = "daily_check",
    signal: str | None = None,
    status: str | None = None,
    score_pct: int | float | None = None,
    entry: str | float | None = None,
    target: str | float | None = None,
    close_price: str | float | None = None,
    logged_at: str | None = None,
):
    """บันทึก 'บทเรียนจากความผิดพลาด' (หรือความสำเร็จ) ลง Google Sheets

    - outcome: WIN / LOSE / DRAW / PENDING
    - self_score: 0-100 (ผู้ใช้ให้คะแนนตัวเอง)
    """
    client = _get_gspread_client()
    sheet_id, worksheet_name = _get_crypto_memory_sheet_config()

    if not client or not sheet_id:
        return False

    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(worksheet_name)
    except Exception:
        # ถ้า worksheet ยังไม่มี: สร้างใหม่อัตโนมัติ
        try:
            sh = client.open_by_key(sheet_id)
            ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=30)
        except Exception as e:
            print(f"❌ Open/Create memory worksheet failed: {e}")
            return False

    headers = [
        "timestamp",
        "year",
        "symbol",
        "mode",
        "signal",
        "status",
        "score_pct",
        "outcome",
        "self_score",
        "entry",
        "target",
        "close_price",
        "mistakes",
        "fix_plan",
        "tags",
    ]

    try:
        first_row = ws.row_values(1)
    except Exception:
        first_row = []

    if not first_row:
        ws.append_row(headers, value_input_option="RAW")

    ts = logged_at or datetime.datetime.now().isoformat(timespec="seconds")
    year = ts[:4]

    # กันลิมิต cell 50k
    def _clip(s, n=20000):
        if s is None:
            return ""
        s = str(s)
        return s if len(s) <= n else s[: n - 40] + "\n... (ตัดข้อความเพราะยาวเกิน)"

    row = [
        ts,
        year,
        str(symbol).upper(),
        mode,
        signal or "",
        status or "",
        float(score_pct) if score_pct is not None and str(score_pct).strip() != "" else "",
        str(outcome).upper(),
        float(self_score) if self_score is not None and str(self_score).strip() != "" else "",
        entry if entry is not None else "",
        target if target is not None else "",
        close_price if close_price is not None else "",
        _clip(mistakes, 20000),
        _clip(fix_plan, 20000),
        _clip(tags, 3000),
    ]

    try:
        ws.append_row(row, value_input_option="RAW")
        return True
    except Exception as e:
        print(f"❌ Append memory row failed: {e}")
        return False


@st.cache_data(show_spinner=False, ttl=60)
def fetch_crypto_memory_rows(year: str | None = None, symbol: str | None = None, limit: int = 400):
    """อ่านบทเรียนจาก Google Sheets แล้วกรองตามปี/เหรียญ (คืน list[dict])"""
    client = _get_gspread_client()
    sheet_id, worksheet_name = _get_crypto_memory_sheet_config()

    if not client or not sheet_id:
        return []

    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(worksheet_name)
        rows = ws.get_all_records()  # list[dict]
    except Exception as e:
        # ถ้ายังไม่มี worksheet ให้ถือว่าไม่มีข้อมูล
        print(f"❌ Read memory worksheet failed: {e}")
        return []

    def _match(row):
        if year and str(row.get("year", "")).strip() != str(year):
            return False
        if symbol and str(row.get("symbol", "")).upper().strip() != str(symbol).upper().strip():
            return False
        return True

    filtered = [r for r in rows if _match(r)]

    # เรียงใหม่สุดก่อน
    def _ts_key(r):
        return str(r.get("timestamp", ""))

    filtered.sort(key=_ts_key, reverse=True)
    return filtered[: max(1, int(limit))]


def summarize_crypto_memory(rows: list[dict]):
    """สรุปสถิติจาก rows"""
    attempts = len(rows)
    wins = sum(1 for r in rows if str(r.get("outcome", "")).upper() == "WIN")
    losses = sum(1 for r in rows if str(r.get("outcome", "")).upper() == "LOSE")
    draws = sum(1 for r in rows if str(r.get("outcome", "")).upper() in ("DRAW", "TIE"))
    winrate = (wins / attempts * 100.0) if attempts else 0.0

    # avg self score
    scores = []
    for r in rows:
        v = r.get("self_score", "")
        try:
            if v != "" and v is not None:
                scores.append(float(str(v).replace("%", "").strip()))
        except Exception:
            pass
    avg_self_score = (sum(scores) / len(scores)) if scores else 0.0

    # Top mistakes (simple frequency by first 120 chars / or tags)
    mistake_counter = collections.Counter()
    tag_counter = collections.Counter()
    for r in rows:
        ms = str(r.get("mistakes", "")).strip()
        if ms:
            key = ms.split("\n")[0][:120].strip()
            if key:
                mistake_counter[key] += 1
        tags = str(r.get("tags", "")).strip()
        if tags:
            # split by comma
            for t in re.split(r"[,\n]+", tags):
                t = t.strip()
                if t:
                    tag_counter[t] += 1

    top_mistakes = mistake_counter.most_common(5)
    top_tags = tag_counter.most_common(8)

    return {
        "attempts": attempts,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "winrate": winrate,
        "avg_self_score": avg_self_score,
        "top_mistakes": top_mistakes,
        "top_tags": top_tags,
    }


def build_crypto_memory_context(symbol: str, year: str | None = None, max_rows: int = 120):
    """สร้าง context สั้นๆ ให้ AI ใช้ 'จำ' ความผิดพลาดตัวเอง

    - เน้น: winrate + top mistakes + top tags
    - จำกัดความยาวเพื่อไม่กินโทเคน
    """
    if not symbol:
        return ""

    if not year:
        year = str(datetime.datetime.now().year)

    rows = fetch_crypto_memory_rows(year=year, symbol=symbol, limit=max_rows)
    if not rows:
        return f"[Memory] ยังไม่มีบทเรียนย้อนหลังของ {symbol} ในปี {year}"

    stats = summarize_crypto_memory(rows)

    # ทำ bullet ของ mistake
    mis_lines = []
    for m, c in stats["top_mistakes"]:
        mis_lines.append(f"- ({c}x) {m}")

    tag_lines = []
    for t, c in stats["top_tags"]:
        tag_lines.append(f"- ({c}x) {t}")

    ctx = f"""
[Personal Memory: Lessons Learned | {symbol} | {year}]
- Attempts: {stats['attempts']}, Wins: {stats['wins']}, Losses: {stats['losses']}, Winrate: {stats['winrate']:.1f}%
- Avg Self Score: {stats['avg_self_score']:.1f}/100

[Most common mistakes]
{chr(10).join(mis_lines) if mis_lines else "- (none logged)"}

[Common tags / contexts]
{chr(10).join(tag_lines) if tag_lines else "- (none logged)"}

Instruction: ถ้ารูปแบบตลาดวันนี้ "คล้าย" กับ mistakes/tags ด้านบน ให้ลด Confidence, เพิ่มคำเตือน, และแนะนำรอ Confirm มากขึ้น
""".strip()

    # clip to ~1800 chars
    return ctx if len(ctx) <= 1800 else ctx[:1750] + "\n...(memory truncated)"



def append_crypto_analysis_to_gsheet(
    *,
    mode: str,
    symbol: str,
    price: float,
    analysis_text: str,
    indicators: dict | None = None,
    news_count: int | None = None,
    fg: dict | None = None,
    generated_at: str | None = None,
):
    """บันทึกผลวิเคราะห์ลง Google Sheets (append row)

    - ถ้า secrets/credentials ไม่ครบ จะ "เงียบ" และ return False
    - กันลิมิต cell 50k chars ของ Google Sheets โดยตัดข้อความ
    """

    client = _get_gspread_client()
    sheet_id, worksheet_name = _get_crypto_sheet_config()

    if not client or not sheet_id:
        return False

    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(worksheet_name)
    except Exception as e:
        print(f"❌ Open worksheet failed: {e}")
        return False

    try:
        # Header (สร้างอัตโนมัติถ้ายังไม่มี)
        headers = [
            "timestamp",
            "mode",
            "symbol",
            "price_thb",
            "rsi",
            "stoch_k",
            "macd",
            "macd_signal",
            "adx",
            "atr",
            "obv_slope",
            "pivot_p",
            "pivot_s1",
            "pivot_r1",
            "support",
            "resistance",
            "news_count",
            "fg_value",
            "fg_classification",
            "analysis",
        ]

        try:
            first_row = ws.row_values(1)
        except Exception:
            first_row = []

        if not first_row:
            ws.append_row(headers, value_input_option="RAW")

        ind = indicators or {}
        fg_val = None
        fg_cls = None
        if isinstance(fg, dict):
            fg_val = fg.get("value")
            fg_cls = fg.get("value_classification")

        ts = generated_at or datetime.datetime.now().isoformat(timespec="seconds")

        # กันลิมิต cell 50k
        if analysis_text and len(analysis_text) > 49000:
            analysis_text = analysis_text[:48900] + "\n... (ตัดข้อความเพราะยาวเกิน Google Sheets)"

        row = [
            ts,
            mode,
            str(symbol).upper(),
            float(price) if price is not None else "",
            ind.get("rsi", ""),
            ind.get("stoch_k", ""),
            ind.get("macd", ""),
            ind.get("macd_signal", ""),
            ind.get("adx", ""),
            ind.get("atr", ""),
            ind.get("obv_slope", ""),
            ind.get("pivot_p", ""),
            ind.get("pivot_s1", ""),
            ind.get("pivot_r1", ""),
            ind.get("support", ""),
            ind.get("resistance", ""),
            int(news_count) if news_count is not None else "",
            fg_val if fg_val is not None else "",
            fg_cls if fg_cls is not None else "",
            analysis_text or "",
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print(f"❌ Append crypto analysis failed: {e}")
        return False

def _extract_drive_file_id(link: str):
    """ดึง file_id จากลิงก์ Google Drive หลายรูปแบบ (view/open/uc/thumbnail)"""
    if not link or not isinstance(link, str):
        return None

    # 1) รูปแบบยอดฮิตของ Drive
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"thumbnail\?id=([a-zA-Z0-9_-]+)",
        r"lh3\.googleusercontent\.com/d/([a-zA-Z0-9_-]+)",
    ]
    for p in patterns:
        m = re.search(p, link)
        if m:
            return m.group(1)

    return None

# --- ฟังก์ชันแปลงลิงก์ Google Drive (รูป) ---
# [FIX] รองรับลิงก์หลายแบบ + ใช้ googleusercontent (เสถียรกว่า thumbnail)
def convert_drive_link(link):
    if not link:
        return link

    # กันกรณีแปะลิงก์โฟลเดอร์มา
    if "drive.google.com" in link and "/folders/" in link:
        return "ERROR: นี่คือลิงก์โฟลเดอร์ครับ! ใช้ได้แค่ลิงก์ไฟล์ (คลิกขวาที่รูป > Share > Copy Link)"

    # ถ้าเป็น Drive / googleusercontent ให้พยายามแปลง
    if "drive.google.com" in link or "googleusercontent.com" in link:
        file_id = _extract_drive_file_id(link)
        if file_id:
            # สูตรที่เสถียรกว่า: ใช้ googleusercontent (Discord/Streamlit ชอบ, รองรับ GIF)
            return f"https://lh3.googleusercontent.com/d/{file_id}"

    return link

# --- ฟังก์ชันแปลงลิงก์ Google Drive (วิดีโอ) ---
def convert_drive_video_link(link):
    if not link:
        return link

    if "drive.google.com" in link:
        if "/folders/" in link:
            return "ERROR: ลิงก์โฟลเดอร์ใช้ไม่ได้ครับ ต้องเป็นลิงก์ไฟล์วิดีโอ"

        file_id = _extract_drive_file_id(link)
        if file_id:
            # แปลงเป็นลิงก์ Preview เพื่อใช้กับ Iframe บนหน้าเว็บ
            return f"https://drive.google.com/file/d/{file_id}/preview"

    return link


def make_clickable(text):
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'<a href="\1" target="_blank" style="color:#A370F7; text-decoration:underline; font-weight:bold;">\1</a>', text)

# --- [NEW] Helper: แปลงลิงก์ Drive เป็นแบบที่ Discord ชอบ (เพื่อให้ GIF ขยับ) ---
def get_discord_friendly_image(url):
    # ถ้าเป็นลิงก์ thumbnail ที่เราแปลงมาแล้ว ให้ดึง ID ออกมาทำเป็น lh3 link
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        # lh3 link รองรับ GIF บน Discord ได้ดีกว่า thumbnail?id=...
        return f"https://lh3.googleusercontent.com/d/{file_id}"
    return url

# --- ฟังก์ชันส่งโพสต์เข้า Discord (Webhook ห้องรวม) ---
def _download_url_bytes(url: str, timeout: int = 15):
    """ดาวน์โหลดไฟล์จาก URL แล้วคืน (bytes, content_type, filename_guess)

    ใช้สำหรับแนบไฟล์เข้า Discord Webhook แบบ attachment://... ให้เสถียรกว่า embed url
    """
    if not url or not isinstance(url, str):
        return None, None, None

    # กันโดนบล็อกง่ายๆ: ใส่ UA
    headers = {"User-Agent": "Mozilla/5.0 (MylaBot; DiscordWebhook)"}
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    r.raise_for_status()

    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    # เดาชื่อไฟล์จาก URL
    filename = url.split("?")[0].split("/")[-1] or "media"
    if "." not in filename:
        # เดา extension จาก content-type
        ext = mimetypes.guess_extension(ctype) or ""
        filename = f"{filename}{ext}"
    return r.content, ctype, filename


def send_post_to_discord(post, max_images: int = 1):
    """ส่งโพสต์เข้า Discord (Webhook ห้องรวม) + รองรับแนบรูปแบบไฟล์ (เสถียร) + เลือกจำนวนรูปได้

    - max_images: เลือกว่าจะส่งรูปกี่รูป (0 = ไม่ส่งรูป)
    - รูปแรก: ใส่เป็น embed image (attachment://...)
    - รูปที่เหลือ: ส่งเป็นข้อความเสริมพร้อมแนบไฟล์
    """
    try:
        webhook_url = st.secrets["general"]["discord_webhook"]
    except Exception:
        print("Webhook URL not found in secrets")
        return

    # --- 1) เตรียมลิงก์รูป ---
    image_urls = []
    if post.get("images"):
        valid_imgs = [img for img in post["images"] if isinstance(img, str) and img.startswith("http")]
        if valid_imgs:
            # แปลงลิงก์แรกให้ Discord Friendly (เดิม) — เผื่อกรณีผู้ใช้ส่ง thumbnail?id=...
            valid_imgs = [get_discord_friendly_image(u) for u in valid_imgs]
            image_urls = valid_imgs[: max(0, int(max_images or 0))]

    # --- 2) เตรียมลิงก์วิดีโอ (Embed เล่น Drive ไม่ได้ — ส่งเป็นลิงก์ให้กด) ---
    video_content = ""
    if post.get("video"):
        video_links = []
        for v in post["video"]:
            if not isinstance(v, str) or not v.startswith("http"):
                continue
            if "youtu" in v:
                video_links.append(f"🎥 [คลิกเพื่อดู YouTube]({v})")
            elif "drive.google.com" in v:
                view_link = v.replace("/preview", "/view")
                video_links.append(f"🎬 [คลิกเพื่อดูคลิปวิดีโอ (Drive)]({view_link})")
            else:
                video_links.append(f"📹 [คลิกเพื่อดูวิดีโอ]({v})")
        if video_links:
            video_content = "\n\n" + "\n".join(video_links)

    final_description = (post.get("content") or "") + video_content

    # --- 3) สร้าง Embed หลัก ---
    embed_data = {
        "username": "Myla Post Update 📢",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "embeds": [{
            "title": f"✨ มีโพสต์ใหม่จากบอส! ({post.get('date','')})",
            "description": final_description,
            "color": int(str(post.get('color', '#A370F7')).replace('#', ''), 16),
            "footer": {"text": f"ID: {post.get('id','')}"}
        }]
    }

    # --- 4) ถ้ามีรูป: แนบเป็นไฟล์เพื่อให้ Discord แสดงแน่นอน ---
    files = None
    if image_urls:
        try:
            b, ctype, filename = _download_url_bytes(image_urls[0])
            if b:
                # Discord webhook: อ้างอิงไฟล์ใน embed ผ่าน attachment://<filename>
                embed_data["embeds"][0]["image"] = {"url": f"attachment://{filename}"}
                files = {"file": (filename, b, ctype or "application/octet-stream")}
        except Exception as e:
            print(f"⚠️ Download/attach image failed: {e}")

    try:
        if files:
            # multipart/form-data: payload_json + file
            requests.post(
                webhook_url,
                data={"payload_json": json.dumps(embed_data)},
                files=files,
                timeout=20,
            )
        else:
            requests.post(webhook_url, json=embed_data, timeout=20)

        # --- 5) ส่งรูปที่เหลือเป็นข้อความเสริม (ถ้ามี) ---
        if len(image_urls) > 1:
            for idx, u in enumerate(image_urls[1:], start=2):
                try:
                    b, ctype, filename = _download_url_bytes(u)
                    if not b:
                        continue
                    requests.post(
                        webhook_url,
                        data={"payload_json": json.dumps({"content": f"📎 รูปเพิ่มเติม ({idx}/{len(image_urls)})"})},
                        files={"file": (filename, b, ctype or "application/octet-stream")},
                        timeout=20,
                    )
                except Exception as e:
                    print(f"⚠️ Failed to send extra image: {e}")

        # [EXTRA] YouTube: ส่งลิงก์เพียวๆ เพิ่ม เพื่อให้เด้ง Player
        if post.get('video'):
            for v in post['video']:
                if isinstance(v, str) and "youtu" in v:
                    requests.post(webhook_url, json={"content": f"📺 **YouTube Player:** {v}"}, timeout=20)

    except Exception as e:
        print(f"Error sending to Discord: {e}")

# --- [ใหม่] ฟังก์ชันส่งจดหมายลับเข้า DM บอสโดยตรง
# (พร้อมระบบสายสืบ + รูป) ---
def send_secret_to_discord(text, sender_info="ไม่ระบุตัวตน (Guest)", avatar_url=None):
    # 1. พยายามดึง Token ของบอท
    try:
        bot_token = st.secrets["discord_bot"]["token"]
    except:
        print("Error: ไม่พบ [discord_bot] token ใน secrets")
        return

    # ID ของ Boss (Dearluxion)
    boss_id = "420947252849410055"

    # Header สำหรับคุยกับ API Discord
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    try:
        # ขั้นตอน A: สร้าง/ขอเลขห้องแชทส่วนตัว (DM Channel) กับบอส
        dm_payload = {"recipient_id": boss_id}
        dm_req = requests.post("https://discord.com/api/v10/users/@me/channels", json=dm_payload, headers=headers)
        
        if dm_req.status_code == 200:
            channel_id = dm_req.json()["id"] # ได้เลขห้องมาแล้ว

            # ขั้นตอน B: เตรียมหน้าตาข้อความ (Embed)
            embed = {
                "title": "💌 มีความลับถูกส่งมาถึงบอส! (Direct Message)",
                "description": f"```{text}```\n\n🕵️ **สายสืบรายงาน:**\nคนส่งคือ: `{sender_info}`", 
                "color": 16738740, # สีชมพู Hot Pink
                "footer": {"text": "ส่งมาจากหน้าเว็บ Small Group (Secret Box)"},
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # [อัปเกรด] ใส่รูปคนส่ง (ถ้ามี)
            if avatar_url:
                embed["thumbnail"] = {"url": avatar_url}

            embed_data = {"embeds": [embed]}
            
            # ขั้นตอน C: ส่งเข้าห้อง DM
            send_req = requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json=embed_data, headers=headers)
            
            if send_req.status_code != 200:
                print(f"Failed to send DM: {send_req.text}")
        else:
            print(f"Failed to open DM Channel: {dm_req.text}")

    except Exception as e:
        print(f"Error logic sending DM: {e}")

# --- Discord Login Functions ---

# 1. ฟังก์ชันสร้างลิงก์ปุ่มกด Login
def get_discord_login_url(client_id, redirect_uri):
    base_url = "https://discord.com/api/oauth2/authorize"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify"
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

# 2. ฟังก์ชันเอารหัส Code ไปแลกเป็นกุญแจเข้าบ้าน (Token)
def exchange_code_for_token(client_id, client_secret, code, redirect_uri):
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    r.raise_for_status()
    return r.json()

# 3. ฟังก์ชันดึงข้อมูลชื่อและรูปโปรไฟล์
def get_discord_user(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://discord.com/api/users/@me", headers=headers)
    r.raise_for_status()
    return r.json()

# --- [NEW] ฟังก์ชันส่งผลวิเคราะห์ Crypto God Mode เข้า Discord ---
def send_crypto_report_to_discord(webhook_url, symbol, price, analysis_text):
    """ส่งผลวิเคราะห์ Crypto God Mode ไปยัง Discord"""

    if not webhook_url:
        print("❌ No Crypto Webhook URL provided")
        return

    # ตัดข้อความถ้ามันยาวเกินลิมิต Discord (4096 chars)
    if len(analysis_text) > 4000:
        analysis_text = analysis_text[:3900] + "... (อ่านต่อในเว็บ)"

    # กำหนดสีตามเนื้อหา (ถ้า Bullish สีเขียว, Bearish สีแดง, อื่นๆ สีทอง)
    embed_color = 16766720 # สีทอง (Gold) ค่าเริ่มต้น
    if "BULLISH" in analysis_text or "น่าเก็บ" in analysis_text:
        embed_color = 5763719 # สีเขียว (Green)
    elif "BEARISH" in analysis_text or "เสี่ยง" in analysis_text:
        embed_color = 15548997 # สีแดง (Red)

    embed_data = {
        "username": "Crypto God Oracle 🔮",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/6001/6001368.png",
        "embeds": [{
            "title": f"💎 God Mode Analysis: {symbol.upper()}",
            "description": analysis_text,
            "color": embed_color,
            "fields": [
                {
                    "name": "💰 ราคาปัจจุบัน",
                    "value": f"฿{price:,.4f} THB",
                    "inline": True
                },
                {
                    "name": "🧠 วิเคราะห์โดย",
                    "value": "Gemini 2.5 (3-Step Reflection)",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Small Group Crypto War Room | {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
            }
        }]
    }

    try:
        requests.post(webhook_url, json=embed_data)
        print(f"✅ Sent {symbol} report to Discord")
    except Exception as e:
        print(f"❌ Failed to send crypto report: {e}")