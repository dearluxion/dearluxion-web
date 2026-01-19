import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import feedparser
import requests
from bs4 import BeautifulSoup

# แปลงชื่อเหรียญให้เป็น Symbol ของ Yahoo Finance
COIN_MAP = {
    "BTC": "BTC-USD",
    "SHIB": "SHIB-USD"
}

# เพิ่ม @st.cache_data เพื่อจำข้อมูลไว้ 5 นาที (300 วิ)
@st.cache_data(ttl=300)
def get_crypto_data(symbol_key, period="6mo", interval="1d"):
    """ดึงข้อมูลกราฟ + คำนวณ Technical Indicators แบบครบเครื่อง"""
    symbol = COIN_MAP.get(symbol_key, "BTC-USD")
    df = yf.download(symbol, period=period, interval=interval)
    
    if df.empty:
        return None

    # คำนวณ Technical Indicators (ใช้ pandas_ta)
    # 1. RSI (บอกว่าซื้อ/ขาย มากเกินไปหรือยัง)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # 2. MACD (บอกเทรนด์และการกลับตัว)
    macd = ta.macd(df['Close'])
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
    
    # 3. Bollinger Bands (บอกความผันผวน)
    bb = ta.bbands(df['Close'], length=20)
    df['BB_UPPER'] = bb['BBU_20_2.0']
    df['BB_LOWER'] = bb['BBL_20_2.0']

    # 4. EMA (เส้นค่าเฉลี่ย)
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

    return df

# เพิ่ม @st.cache_data เพื่อจำข่าวไว้ 10 นาที
@st.cache_data(ttl=600)
def get_crypto_news(symbol_key):
    """ดูดข่าวล่าสุดจาก CoinTelegraph (RSS)"""
    rss_url = "https://cointelegraph.com/rss"
    feed = feedparser.parse(rss_url)
    
    news_list = []
    keyword = symbol_key.lower()
    
    count = 0
    for entry in feed.entries:
        # กรองข่าวเฉพาะเหรียญที่เราสนใจ หรือข่าวตลาดรวม (Bitcoin/Market)
        title = entry.title.lower()
        summary = entry.summary.lower()
        
        if keyword in title or keyword in summary or "market" in title or "bitcoin" in title:
            news_list.append(f"- {entry.title} ({entry.published})")
            count += 1
            if count >= 5: break # เอาแค่ 5 ข่าวล่าสุดพอ เดี๋ยว Token เต็ม
            
    if not news_list:
        return "ไม่มีข่าวสำคัญในช่วง 24 ชม. ที่ผ่านมา ให้วิเคราะห์จากกราฟเป็นหลัก"
    
    return "\n".join(news_list)

def get_fear_and_greed():
    """ดึงดัชนี Fear & Greed (อารมณ์ตลาด)"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1")
        data = r.json()
        return data['data'][0]
    except:
        return {"value_classification": "Unknown", "value": "50"}