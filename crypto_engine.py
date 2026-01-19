import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import feedparser
import requests

# [UPDATE] ใช้ Ticker หลักเป็น USD เพื่อความแม่นยำของกราฟ
COIN_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "BNB": "BNB-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "PEPE": "PEPE-USD",
    "SHIB": "SHIB-USD"
}

@st.cache_data(ttl=300)
def get_exchange_rate():
    try:
        # ดึงค่าเงินบาทล่าสุดจาก Yahoo Finance
        ticker = yf.Ticker("USDTHB=X")
        # ดึงย้อนหลัง 1 วัน เอาตัวล่าสุด
        df = ticker.history(period="1d")
        if not df.empty:
            rate = df['Close'].iloc[-1]
            return float(rate)
        return 34.0 # ค่าสำรองกันตาย
    except:
        return 34.0

@st.cache_data(ttl=300)
def get_crypto_data(symbol_key, period="2y", interval="1d"):
    # 1. ดึงข้อมูล Crypto เป็น USD
    symbol = COIN_MAP.get(symbol_key, "BTC-USD")
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    
    if df.empty:
        return None

    # [Fix MultiIndex] แก้ปัญหาหัวตารางซ้อนกัน
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except: 
        pass

    if 'Close' not in df.columns:
        return None

    # 2. [NEW] แปลงเป็นเงินบาท (THB)
    # ดึงเรทเงินบาท
    thb_rate = get_exchange_rate()
    
    # คูณค่าเงินเข้าไปในคอลัมน์ราคาต่างๆ
    cols_to_convert = ['Open', 'High', 'Low', 'Close']
    for c in cols_to_convert:
        if c in df.columns:
            df[c] = df[c] * thb_rate

    # 3. คำนวณอินดิเคเตอร์ (คำนวณจากราคาไทยที่แปลงแล้ว)
    # RSI
    try:
        df['RSI'] = ta.rsi(df['Close'], length=14)
    except: 
        df['RSI'] = 50
    
    # MACD
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