import datetime
import json
import ai_manager as ai

def _collect_mistakes_text(rows: list[dict], max_items: int = 30) -> str:
    parts = []
    for r in rows[:max_items]:
        ts = r.get("timestamp", "")
        cat = r.get("category", "")
        task = r.get("task", "")
        m = (r.get("mistakes") or "").strip()
        if not m:
            continue
        parts.append(f"- [{ts}] ({cat}) {task}: {m}")
    return "\n".join(parts).strip()

def generate_learning_plan(*, recent_rows: list[dict], current_mistakes: str, year: int, category: str) -> str:
    """สรุป 'บทเรียน/แผนซ้อม' จากความผิดพลาด (ใช้ AI)"""
    if not ai.check_ready():
        return "⚠️ ระบบ AI ยังไม่พร้อม"

    history = _collect_mistakes_text(recent_rows, max_items=25)
    cur = (current_mistakes or "").strip()

    prompt = f"""คุณคือโค้ชติวเข้มที่เน้น 'เรียนรู้จากความผิดพลาด' แบบเป็นระบบ
ภารกิจ: สร้างแผนปรับปรุงจากบันทึกการบ้านในปี {year} หมวด {category}

ข้อมูลความผิดพลาดล่าสุด:
{cur if cur else "(ยังไม่ได้กรอก)"}

ประวัติความผิดพลาดย้อนหลัง (ย่อ):
{history if history else "(ยังไม่มีประวัติ)"}

ให้ตอบเป็นภาษาไทย โดยจัดรูปแบบดังนี้:
1) สรุป Pattern ความผิดพลาด (3-7 ข้อ)
2) Checklist ก่อนส่งคำตอบครั้งหน้า (5-12 ข้อ)
3) แผนซ้อม 7 วัน (Day 1-7) แบบทำได้จริง
4) เกณฑ์วัดผล (Metrics) เพื่อคำนวณ 'อัตราชนะ' และการพัฒนา
"""

    try:
        res = ai._safe_generate_content([prompt])
        return (res.text or "").strip()
    except Exception as e:
        return f"⚠️ AI สรุปบทเรียนไม่สำเร็จ: {e}"
