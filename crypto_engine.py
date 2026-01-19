import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import feedparser
import requests

COIN_MAP = {
    "BTC": "BTC-USD",
    "SHIB": "SHIB-USD"
}

@st.cache_data(ttl=300)
def get_crypto_data(symbol_key, period="6mo", interval="1d"):
    symbol = COIN_MAP.get(symbol_key, "BTC-USD")
    
    # [Tweak] เพิ่ม auto_adjust=True เพื่อให้ได้กราฟที่คลีนขึ้น
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    
    if df.empty:
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
    
    # คำนวณ MACD (จุดที่เคย Error)
    try:
        macd = ta.macd(df['Close'])
        if macd is not None and not macd.empty:
            # ดึงชื่อคอลัมน์อัตโนมัติ (กันชื่อเปลี่ยน)
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