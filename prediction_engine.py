"""
⚖️ PREDICTION ENGINE (Backtest System)
ตัวระบบตรวจวัดความแม่นยำของการทำนายเหรียญ
"""

import data_manager as dm
import crypto_engine as ce
import datetime
import requests

def check_accuracy_and_broadcast(webhook_url):
    """
    ฟังก์ชันตรวจการบ้าน:
    1. ดึงโพสต์ที่ Pending ของวันนี้
    2. เช็คราคาปัจจุบัน
    3. ให้คะแนน
    4. ส่งเข้า Discord
    """
    pending_items = dm.get_pending_predictions()
    
    if not pending_items:
        return "ไม่มีรายการค้างตรวจ (หรือตรวจไปหมดแล้ว)"

    summary_report = []
    total_accuracy = 0
    win_count = 0
    
    for item in pending_items:
        symbol = item.get('symbol', 'N/A')
        signal = item.get('signal', 'NEUTRAL').upper()
        
        try:
            entry = float(item.get('entry', 0))
            target = float(item.get('target', 0))
            stoploss = float(item.get('stoploss', 0))
            row_idx = item.get('row_index', 0)
        except:
            continue

        # ดึงราคาปัจจุบัน
        try:
            df = ce.get_crypto_data(symbol)
            if df is None or len(df) == 0:
                continue
            current_price = df['Close'].iloc[-1]
        except Exception as e:
            print(f"Price fetch error for {symbol}: {e}")
            continue

        # Logic การให้คะแนน
        score = 0
        status = "PENDING"
        
        # กรณีทายขาขึ้น (BULLISH)
        if "BULL" in signal:
            if current_price >= target:
                score = 100
                status = "WIN 🏆"
                win_count += 1
            elif current_price <= stoploss:
                score = 0
                status = "LOSS 💀"
            elif current_price > entry:
                # คำนวณ % ความสำเร็จตามระยะทาง
                total_dist = target - entry
                if total_dist > 0:
                    current_dist = current_price - entry
                    score = min(99, int((current_dist / total_dist) * 100))
                status = "RUNNING 🏃"
            else:
                score = 0
                status = "DRAW/WAIT ⏳"

        # กรณีทายขาลง (BEARISH)
        elif "BEAR" in signal:
            if current_price <= target:
                score = 100
                status = "WIN 🏆"
                win_count += 1
            elif current_price >= stoploss:
                score = 0
                status = "LOSS 💀"
            elif current_price < entry:
                total_dist = entry - target
                if total_dist > 0:
                    current_dist = entry - current_price
                    score = min(99, int((current_dist / total_dist) * 100))
                status = "RUNNING 🏃"
            else:
                score = 0
                status = "DRAW/WAIT ⏳"

        # บันทึกผล
        dm.update_prediction_result(row_idx, status, score, current_price)
        
        # เพิ่มในรายงาน
        icon = "🟢" if score >= 80 else "🟡" if score >= 40 else "🔴"
        summary_report.append({
            "symbol": symbol,
            "signal": signal,
            "status": status,
            "score": score,
            "icon": icon,
            "price": current_price,
            "entry": entry,
            "target": target
        })
        
        total_accuracy += score

    # คำนวณค่าเฉลี่ย
    avg_accuracy = total_accuracy // len(summary_report) if summary_report else 0
    win_rate = (win_count / len(summary_report) * 100) if summary_report else 0

    # ส่งเข้า Discord
    if summary_report:
        # สร้างรายงาน Text
        report_lines = []
        for item in summary_report:
            line = f"{item['icon']} **{item['symbol']}** ({item['signal']}) | {item['status']} | ความแม่นยำ: **{item['score']}%**\n"
            line += f"   Entry: {item['entry']:,.2f} → Target: {item['target']:,.2f} | Current: {item['price']:,.2f}"
            report_lines.append(line)
        
        final_text = "\n".join(report_lines)
        
        # คำนวณเวลาไทย (UTC + 7 ชม.)
        th_time = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        
        embed_data = {
            "username": "AI Judge ⚖️ (Daily Recap)",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2643/2643644.png",
            "embeds": [{
                "title": f"📝 สรุปผลการทำนาย (Backtest) - {th_time.strftime('%d/%m/%Y')}",
                "description": final_text,
                "color": 3447003,  # Blue
                "fields": [
                    {
                        "name": "📊 สถิติทั้งวัน",
                        "value": f"**กำลังตรวจ:** {len(summary_report)} รายการ\n**ถูกต้องเฉลี่ย:** {avg_accuracy}%\n**Win Rate:** {win_rate:.1f}%",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"ระบบตรวจวัดผลอัตโนมัติ | เวลา: {th_time.strftime('%H:%M:%S')} น."
                }
            }]
        }
        
        try:
            requests.post(webhook_url, json=embed_data)
        except Exception as e:
            print(f"Discord send error: {e}")
        
        return f"✅ ตรวจเสร็จสิ้น {len(summary_report)} รายการ | เฉลี่ย {avg_accuracy}% | Sent to Discord!"
    
    return "ไม่พบข้อมูลใหม่"
