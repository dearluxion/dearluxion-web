import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import feedparser
import requests

# [UPDATE] เปลี่ยนรายชื่อเหรียญเป็นคู่เงินบาท (THB)
COIN_MAP = {
    "BTC": "BTC-THB",
    "ETH": "ETH-THB",
    "BNB": "BNB-THB",
    "SOL": "SOL-THB",
    "XRP": "XRP-THB",
    "DOGE": "DOGE-THB",
    "PEPE": "PEPE-THB", # หมายเหตุ: บางครั้ง PEPE/SHIB ใน Yahoo Finance แบบ THB อาจหาข้อมูลยาก ถ้าไม่ขึ้นกราฟอาจต้องใช้ USD
    "SHIB": "SHIB-THB"
}

@st.cache_data(ttl=300)
def get_crypto_data(symbol_key, period="2y", interval="1d"):
    symbol = COIN_MAP.get(symbol_key, "BTC-THB")
    
    # [Tweak] เพิ่ม auto_adjust=True เพื่อให้ได้กราฟที่คลีนขึ้น
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    
    if df.empty:
        # Fallback: ถ้าหา THB ไม่เจอ ลองหา USD แล้วคูณอัตราแลกเปลี่ยน (แบบคร่าวๆ หรือแจ้งเตือน)
        # แต่ในที่นี้จะ return None ไปก่อนเพื่อให้ App แจ้งว่าดึงข้อมูลไม่ได้
        return None

    # [Fix MultiIndex] แก้ปัญหาหัวตารางซ้อนกัน 2 ชั้น
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except: 
        pass

    # เช็คว่ามีคอลัมน์ Close ไหม ถ้าไม่มีให้จบการทำงาน
    if 'Close' not in df.columns:
        return None

    # คำนวณ RSI
    try:
        df['RSI'] = ta.rsi(df['Close'], length=14)
    except: 
        df['RSI'] = 50
    
    # คำนวณ MACD
    try:
        macd = ta.macd(df['Close'])
        if macd is not None and not macd.empty:
            df['MACD'] = macd.iloc[:, 0] 
            df['MACD_SIGNAL'] = macd.iloc[:, 2]
        else:
            df['MACD'] = 0
            df['MACD_SIGNAL'] = 0
    except:
        df['MACD'] = 0
        df['MACD_SIGNAL'] = 0
    
    # Bollinger Bands
    try:
        bb = ta.bbands(df['Close'], length=20)
        if bb is not None and not bb.empty:
            df['BB_UPPER'] = bb.iloc[:, 0]
            df['BB_LOWER'] = bb.iloc[:, 2]
    except: 
        pass

    # EMA
    try:
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)
    except: 
        pass

    return df

@st.cache_data(ttl=600)
def get_crypto_news(symbol_key):
    try:
        rss_url = "https://cointelegraph.com/rss"
        feed = feedparser.parse(rss_url)
        news_list = []
        keyword = symbol_key.lower()
        
        count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            summary = entry.summary.lower()
            if keyword in title or keyword in summary or "market" in title or "bitcoin" in title:
                news_list.append(f"- {entry.title} ({entry.published})")
                count += 1
                if count >= 5: 
                    break 
                
        if not news_list: 
            return "ไม่มีข่าวสำคัญในช่วง 24 ชม. ให้วิเคราะห์จากกราฟเป็นหลัก"
        return "\n".join(news_list)
    except:
        return "ไม่สามารถดึงข่าวได้ (RSS Error)"

def get_fear_and_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = r.json()
        return data['data'][0]
    except:
        return {"value_classification": "Unknown", "value": "50"}